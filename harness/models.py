from dataclasses import dataclass , field
from typing import Any


# 工具调用
@dataclass
class ToolCall:
    """模型请求执行的一次工具调用"""
    call_id: str    # 本次调用的唯一ID，工具结果按此ID回传
    name: str       # 要调用的工具名
    arguments: dict[str , Any]    # 模型给出的工具参数(原始JSON对象)

# 模型结果  
@dataclass
class ModelResult:
    """模型单次生成的结果"""
    text: str    # 模型输出的文本内容
    tool_calls: list[ToolCall] = field(default_factory=list)    # 模型请求的工具调用列表(可能为空)
    response_id : str | None = None    # 响应ID，用于下一轮请求续接上下文

@dataclass
class RunResult:
    """模型运行结果"""
    output: str
    steps: int
    response_id: str | None = None


