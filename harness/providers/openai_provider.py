import json
from openai import OpenAI
from harness.models import ModelResult , ToolCall, ModelUsage 

class OpenAIProvider:
    """OpenAI 提供方(基于 responses 接口)"""

    def __init__(self , model: str , observability , api_key: str = None , base_url: str = None , metrics=None) -> None:
        """初始化。
        参数 model: 模型名(默认 gpt-3.5-turbo)
        参数 api_key: API 密钥
        参数 base_url: 接口地址
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.observability = observability
        self.metrics = metrics

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
    async def generate(self, * ,input_data , tools : list[dict] ,instructions: str | None = None , previous_response_id: str | None = None) -> ModelResult:
        """调用模型生成一轮结果(同步)。
        参数 input_data: 输入内容(字符串或工具结果列表，直接透传)
        参数 tools: 工具 schema 列表
        参数 instructions: 指令(服务端自动续接)
        参数 previous_response_id: 上一轮响应ID(服务端自动续接)
        返回: ModelResult(文本 + 工具调用 + 响应ID)
        """

        with self.observability.span(
            "gen_ai.generate",
            {
                "gen_ai.operation.name": "generate",
                "gen_ai.request.model": self.model,
                "gen_ai.provider.name": "openai",
            },
        ) as span:

            response = await self.client.responses.create(
                model=self.model,
                input=input_data,
                tools=tools,
                instructions=instructions,
                previous_response_id=previous_response_id
            )

            # 记录使用情况
            usage = response.usage
            input_tokens = usage.input_tokens if usage is not None else 0
            output_tokens = usage.output_tokens if usage is not None else 0
            total_tokens = usage.total_tokens if usage is not None else 0
            cached_input_tokens = 0

            # 记录缓存输入token数
            if usage is not None and usage.input_tokens_details is not None:
                cached_input_tokens = usage.input_tokens_details.cached_tokens or 0

            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
            span.set_attribute("gen_ai.response.id", response.id)

            # 记录指标
            metric_attributes = {
                "model": self.model,
                "provider": "openai",
            }
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
                usage=ModelUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cached_input_tokens=cached_input_tokens,
                )
            )