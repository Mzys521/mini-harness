import json
from time import perf_counter

from openai import AsyncOpenAI
from harness.models import ModelResult , ToolCall, ModelUsage 

class OpenAIProvider:
    """OpenAI 提供方(基于 responses 接口)"""

    def __init__(self , model: str , observability , api_key: str = None , base_url: str = None , metrics=None) -> None:
        """初始化。
        参数 model: 模型名(默认 gpt-3.5-turbo)
        参数 api_key: API 密钥
        参数 base_url: 接口地址
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.observability = observability
        self.metrics = metrics
        self.store_responses = True

    # 已经在 0.5.0 版本中弃用 将在 0.7.0 版本中删除
    # # 转换为 OpenAI 输入
    # def _to_provider_input(context: ModelContext ,) -> list[dict]:
    #     """把 ModelContext 转成模型输入列表。
    #     参数 context: 已构建的模型上下文
    #     返回: [{"role","content","name"}, ...] 列表
    #     注意: 缺少 self 参数，且 Message 无 name 字段，当前未被调用
    #     """
    #     return [
    #         {
    #             "role": message.role.value,
    #             "content": message.content,
    #             "name": message.name,
    #         }
    #         for message in context.messages
    #     ]
    
    # 发送模型请求
    async def generate(self, * ,input_data , tools : list[dict] ,instructions: str | None = None , previous_response_id: str | None = None , on_delta = None) -> ModelResult:
        """调用模型生成一轮结果(流式)。
        参数 input_data: 输入内容(字符串或工具结果列表，直接透传)
        参数 tools: 工具 schema 列表
        参数 instructions: 指令(服务端自动续接)
        参数 previous_response_id: 上一轮响应ID(服务端自动续接)
        参数 on_delta: 可选增量回调，每收到一段文本增量立即调用一次
        返回: ModelResult(文本 + 工具调用 + 响应ID)
        """

        # Responses 接口耗时基线：必须在下发请求前取样。
        started = perf_counter()

        with self.observability.span(
            "gen_ai.generate",
            {
                "gen_ai.operation.name": "generate",
                "gen_ai.request.model": self.model,
                "gen_ai.provider.name": "openai",
            },
        ) as span:

            stream = await self.client.responses.create(
                model=self.model,
                input=input_data,
                tools=tools,
                instructions=instructions,
                previous_response_id=previous_response_id,
                stream=True,
                store=self.store_responses,
            )

            response = None

            async for event in stream:
                if event.type == "response.output_text.delta":
                    if on_delta is not None:
                        on_delta(event.delta)
                elif event.type == "response.completed":
                    # 事件的 response 与一次性调用返回的对象同构，后续解析逻辑完全复用。
                    response = event.response

            if response is None:
                raise RuntimeError("OpenAI responses 流在结束时没有返回 response.completed 事件")

            # 记录使用情况
            usage = response.usage
            input_tokens = usage.input_tokens if usage is not None else 0
            output_tokens = usage.output_tokens if usage is not None else 0
            total_tokens = usage.total_tokens if usage is not None else 0
            cached_input_tokens = 0

            details = getattr(usage, "input_tokens_details", None)
            cache_count = getattr(details, "cached_tokens", None)
            cached_input_tokens = cache_count or 0

            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
            span.set_attribute("gen_ai.response.id", response.id)

            # 记录指标
            metric_attributes = {
                "model": self.model,
                "provider": "openai",
            }
            if self.metrics is not None:
                self.metrics.model_input_tokens.add(input_tokens, metric_attributes)
                self.metrics.model_output_tokens.add(output_tokens, metric_attributes)
                self.metrics.model_duration.record(perf_counter() - started, metric_attributes)

            tool_calls : list[ToolCall] =[]

            for item in response.output:
                if item.type != "function_call":
                    continue    # 只收集工具调用项，跳过其他输出

                tool_calls.append(
                    ToolCall(
                        call_id=item.call_id,
                        name=item.name,
                        arguments=json.loads(item.arguments)
                    )
                )

            return ModelResult(
                text = response.output_text,
                tool_calls=tool_calls,
                response_id=response.id,
                cache_usage_reported=cache_count is not None,
                usage=ModelUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cached_input_tokens=cached_input_tokens,
                )
            )
