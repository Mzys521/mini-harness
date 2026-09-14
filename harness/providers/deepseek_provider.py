import json
from openai import OpenAI
from harness.models import ModelResult , ToolCall

class DeepSeekProvider:
    """DeepSeek 提供方(基于 OpenAI SDK 的 chat 接口，本地维护历史模拟有状态会话)"""

    def __init__(self , model: str = "deepseek-chat" , api_key: str = None , base_url: str = None) -> None:
        """初始化。
        参数 model: 模型名(默认 deepseek-chat)
        参数 api_key: API 密钥
        参数 base_url: 接口地址(默认 https://api.deepseek.com)
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url or "https://api.deepseek.com")
        self.model = model
        self._histories : dict[str , list[dict]] = {}    # 本地历史: response_id -> messages


    def generate(self, * ,input_data , tools : list[dict] , previous_response_id: str | None = None) -> ModelResult:
        """调用模型生成一轮结果(同步)。
        参数 input_data: 用户输入字符串，或上一轮工具结果列表
        参数 tools: OpenAI 格式工具 schema 列表
        参数 previous_response_id: 上一轮响应ID，用于续接历史
        返回: ModelResult(文本 + 工具调用 + 新响应ID)
        """

        # chat 接口无状态，用本地历史模拟 previous_response_id 的续接
        messages = list(self._histories.get(previous_response_id, [])) if previous_response_id else []

        if isinstance(input_data, str):
            messages.append({"role": "user", "content": input_data})
        else:
            for item in input_data:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": item["call_id"],
                        "content": item["output"],
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

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=chat_tools,
        )

        message = response.choices[0].message

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
            response_id=response_id
        )