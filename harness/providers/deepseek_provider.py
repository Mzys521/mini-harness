import json
import os
from contextlib import nullcontext
from time import perf_counter

from openai import OpenAI

from harness.models import ModelResult , ToolCall, ModelUsage

class DeepSeekProvider:
    """DeepSeek 提供方(基于 OpenAI SDK 的 chat 接口，本地维护历史模拟有状态会话)"""

    def __init__(self , model: str | None = None , observability=None , metrics=None , api_key: str = None , base_url: str = None ) -> None:
        """初始化。
        参数 model: 模型名(默认读环境变量 DEEPSEEK_MODEL)
        参数 observability: 可观测性入口，用于包裹生成调用
        参数 metrics: 指标采集器，用于 token 与耗时统计
        参数 api_key: API 密钥(默认读环境变量 DEEPSEEK_API_KEY)
        参数 base_url: 接口地址(默认读环境变量 DEEPSEEK_BASE_URL)
        """
        self.client = OpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"), 
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL")
        )
        self.model = model or os.getenv("DEEPSEEK_MODEL")
        self.observability = observability
        self.metrics = metrics
        self._histories : dict[str , list[dict]] = {}    # 本地历史: response_id -> messages


    # 发送模型请求
    async def generate(self, * ,input_data , tools : list[dict] ,instructions: str | None = None , previous_response_id: str | None = None) -> ModelResult:
        """调用模型生成一轮结果(同步)。
        参数 input_data: 用户输入字符串，或上一轮工具结果列表
        参数 tools: OpenAI 格式工具 schema 列表
        参数 instructions: 指令(chat 接口下转为首轮 system 消息)
        参数 previous_response_id: 上一轮响应ID，用于续接历史
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

        with span_context as span:

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=chat_tools,
            )

            message = response.choices[0].message

            # 记录使用情况(chat 接口用量字段)
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage is not None else 0
            output_tokens = usage.completion_tokens if usage is not None else 0
            total_tokens = usage.total_tokens if usage is not None else 0
            cached_input_tokens = 0

            # 记录缓存输入token数
            if usage is not None and usage.prompt_tokens_details is not None:
                cached_input_tokens = usage.prompt_tokens_details.cached_tokens or 0

            if span is not None:
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                span.set_attribute("gen_ai.response.id", response.id)

            # 记录指标
            if self.metrics is not None:
                metric_attributes = {
                    "model": self.model,
                    "provider": "deepseek",
                }
                self.metrics.model_input_tokens.add(input_tokens, metric_attributes)
                self.metrics.model_output_tokens.add(output_tokens, metric_attributes)
                self.metrics.model_duration.record(perf_counter() - started, metric_attributes)

            tool_calls : list[ToolCall] =[]

            for item in message.tool_calls or []:
                tool_calls.append(
                    ToolCall(
                        call_id=item.id,
                        name=item.function.name,
                        arguments=json.loads(item.function.arguments)
                    )
                )

        messages.append(message)

        response_id = response.id
        self._histories[response_id] = messages    # 以本次响应ID保存完整历史，供下一轮续接

        return ModelResult(
            text = message.content or "",
            tool_calls=tool_calls,
            response_id=response_id,
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cached_input_tokens=cached_input_tokens,
            )
        )