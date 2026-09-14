import json
from openai import OpenAI
from harness.models import ModelResult , ToolCall
from harness.context.models import ModelContext

class OpenAIProvider:
    """OpenAI 提供方(基于 responses 接口)"""

    def __init__(self , model: str = "gpt-3.5-turbo" , api_key: str = None , base_url: str = None) -> None:
        """初始化。
        参数 model: 模型名(默认 gpt-3.5-turbo)
        参数 api_key: API 密钥
        参数 base_url: 接口地址
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    # 转换为 OpenAI 输入
    def _to_provider_input(context: ModelContext ,) -> list[dict]:
        """把 ModelContext 转成模型输入列表。
        参数 context: 已构建的模型上下文
        返回: [{"role","content","name"}, ...] 列表
        注意: 缺少 self 参数，且 Message 无 name 字段，当前未被调用
        """
        return [
            {
                "role": message.role.value,
                "content": message.content,
                "name": message.name,
            }
            for message in context.messages
        ]
    
    # 发送模型请求
    def generate(self, * ,input_data , tools : list[dict] , previous_response_id: str | None = None) -> ModelResult:
        """调用模型生成一轮结果(同步)。
        参数 input_data: 输入内容(字符串或工具结果列表，直接透传)
        参数 tools: 工具 schema 列表
        参数 previous_response_id: 上一轮响应ID(服务端自动续接)
        返回: ModelResult(文本 + 工具调用 + 响应ID)
        """

        response = self.client.responses.create(
            model=self.model,
            input=input_data,
            tools=tools,
            previous_response_id=previous_response_id
        )

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
            response_id=response.id
        )