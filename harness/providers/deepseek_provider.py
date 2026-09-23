import json
import os
from contextlib import nullcontext
from time import perf_counter
from typing import Callable

from openai import AsyncOpenAI

from harness.models import ModelResult , ToolCall, ModelUsage

class DeepSeekProvider:
    """DeepSeek 提供方(基于 OpenAI SDK 的 chat 接口，本地维护历史模拟有状态会话)

    使用 AsyncOpenAI + stream=True：模型输出按增量回调给调用方（前端流式显示），
    同时不阻塞事件循环——这一点对同一进程里的 SSE 推送是必需的。
    """

    def __init__(self , model: str | None = None , observability=None , metrics=None , api_key: str = None , base_url: str = None ) -> None:
        """初始化。
        参数 model: 模型名(默认读环境变量 DEEPSEEK_MODEL)
        参数 observability: 可观测性入口，用于包裹生成调用
        参数 metrics: 指标采集器，用于 token 与耗时统计
        参数 api_key: API 密钥(默认读环境变量 DEEPSEEK_API_KEY)
        参数 base_url: 接口地址(默认读环境变量 DEEPSEEK_BASE_URL)
        """
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"), 
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL")
        )
        self.model = model or os.getenv("DEEPSEEK_MODEL")
        self.observability = observability
        self.metrics = metrics
        self.store_responses = True
        self._histories : dict[str , list[dict]] = {}    # 本地历史: response_id -> messages


    @staticmethod
    def _accumulate_tool_calls(slots: dict[int , dict]) -> tuple[list[ToolCall] , list[dict]]:
        """把流式分片的工具调用还原成 ToolCall 与「可回传给 chat 接口」的原始形态。"""
        tool_calls : list[ToolCall] = []
        raw_calls : list[dict] = []

        for index in sorted(slots):
            slot = slots[index]
            raw = slot["arguments"] or "{}"
            try:
                arguments = json.loads(raw) if raw.strip() else {}
            except ValueError:
                # 参数不是合法 JSON 时交给工具执行器做 Schema 校验，而不是让整次运行崩溃。
                arguments = {"__raw_arguments__": raw}
            if not isinstance(arguments, dict):
                arguments = {"__raw_arguments__": raw}

            tool_calls.append(
                ToolCall(
                    call_id=slot["id"] or f"call_{index}",
                    name=slot["name"],
                    arguments=arguments,
                )
            )
            raw_calls.append(
                {
                    "id": slot["id"] or f"call_{index}",
                    "type": "function",
                    "function": {"name": slot["name"], "arguments": raw},
                }
            )

        return tool_calls , raw_calls


    # 发送模型请求
    async def generate(self, * ,input_data , tools : list[dict] ,instructions: str | None = None , previous_response_id: str | None = None , on_delta: Callable[[str] , None] | None = None) -> ModelResult:
        """调用模型生成一轮结果(流式)。
        参数 input_data: 用户输入字符串，或上一轮工具结果列表
        参数 tools: OpenAI 格式工具 schema 列表
        参数 instructions: 指令(chat 接口下转为首轮 system 消息)
        参数 previous_response_id: 上一轮响应ID，用于续接历史
        参数 on_delta: 可选增量回调，每收到一段文本增量立即调用一次
        返回: ModelResult(文本 + 工具调用 + 新响应ID + 用量)
        """

        # chat 接口无状态，用本地历史模拟 previous_response_id 的续接
        messages = list(self._histories.get(previous_response_id, [])) if previous_response_id else []

        # chat 接口无 instructions 参数，首轮以 system 消息注入
        if instructions and not messages:
            messages.append({"role": "system", "content": instructions})

        if isinstance(input_data, str):
            messages.append({"role": "user", "content": input_data})
        else:
            for item in input_data:
                # 工具结果 → role=tool；普通对话消息 → 直接透传 role/content
                if item.get("type") == "function_call_output":
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": item["call_id"],
                            "content": item["output"],
                        }
                    )
                else:
                    messages.append(
                        {
                            "role": item["role"],
                            "content": item["content"],
                        }
                    )

        # chat 接口的工具格式需要嵌套在 function 字段里
        chat_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for tool in tools
        ]

        # 未接入观测时退化为空上下文，保持与 OpenAI 提供方一致的调用结构
        span_context = (
            self.observability.span(
                "gen_ai.generate",
                {
                    "gen_ai.operation.name": "generate",
                    "gen_ai.request.model": self.model,
                    "gen_ai.provider.name": "deepseek",
                },
            )
            if self.observability is not None
            else nullcontext(None)
        )

        started = perf_counter()
        text_parts : list[str] = []
        slots : dict[int , dict] = {}
        response_id : str | None = None
        usage = None

        with span_context as span:

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=chat_tools,
                stream=True,
                # 流式响应默认不带用量；DeepSeek 与 OpenAI 都支持显式索取。
                stream_options={"include_usage": True},
            )

            async for chunk in stream:
                if response_id is None and getattr(chunk, "id", None):
                    response_id = chunk.id
                if getattr(chunk, "usage", None) is not None:
                    usage = chunk.usage
                if not chunk.choices:
                    # include_usage 的收尾分片只有 usage，没有 choice。
                    continue

                delta = chunk.choices[0].delta
                if delta is None:
                    continue

                if delta.content:
                    text_parts.append(delta.content)
                    if on_delta is not None:
                        on_delta(delta.content)

                for item in delta.tool_calls or []:
                    # 工具调用按 index 分片：首片给 id/name，后续片只给 arguments 片段。
                    index = item.index if item.index is not None else 0
                    slot = slots.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if item.id:
                        slot["id"] = item.id
                    if item.function is not None:
                        if item.function.name:
                            slot["name"] = item.function.name
                        if item.function.arguments:
                            slot["arguments"] += item.function.arguments

            text = "".join(text_parts)
            tool_calls , raw_calls = self._accumulate_tool_calls(slots)

            # 记录使用情况(chat 接口用量字段)
            input_tokens = usage.prompt_tokens if usage is not None else 0
            output_tokens = usage.completion_tokens if usage is not None else 0
            total_tokens = usage.total_tokens if usage is not None else 0
            cached_input_tokens = 0

            # 兼容 DeepSeek 原生缓存字段及 OpenAI 兼容字段。
            cache_count = getattr(usage, "prompt_cache_hit_tokens", None)
            if cache_count is None:
                details = getattr(usage, "prompt_tokens_details", None)
                cache_count = getattr(details, "cached_tokens", None)
            cached_input_tokens = cache_count or 0

            if span is not None:
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                span.set_attribute("gen_ai.response.id", response_id)

            # 记录指标
            if self.metrics is not None:
                metric_attributes = {
                    "model": self.model,
                    "provider": "deepseek",
                }
                self.metrics.model_input_tokens.add(input_tokens, metric_attributes)
                self.metrics.model_output_tokens.add(output_tokens, metric_attributes)
                self.metrics.model_duration.record(perf_counter() - started, metric_attributes)

        # 下一轮要回给 chat 接口的 assistant 消息必须带上 tool_calls 原始分片，
        # 否则 role=tool 的结果无法通过 tool_call_id 对应上。
        # 只有工具调用、没有正文时 content 用 null，这是 chat 接口的规范形态。
        assistant_message : dict = {"role": "assistant", "content": text or None}
        if raw_calls:
            assistant_message["tool_calls"] = raw_calls
        messages.append(assistant_message)

        if response_id is not None and self.store_responses:
            self._histories[response_id] = messages    # 以本次响应ID保存完整历史，供下一轮续接

        return ModelResult(
            text = text,
            tool_calls=tool_calls,
            response_id=response_id,
            cache_usage_reported=cache_count is not None,
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cached_input_tokens=cached_input_tokens,
            )
        )
