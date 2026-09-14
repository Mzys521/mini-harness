from dataclasses import dataclass , asdict
from enum import StrEnum
from typing import Any
import json

class ToolStatus(StrEnum):
    """工具执行的终态枚举"""
    SUCCESS = "success"    # 执行成功
    INVALID_ARGUMENTS = "invalid_argument"    # 参数校验失败
    NOT_FOUND = "not_found"    # 工具不存在
    PERMISSION_DENIED = "permission_denied"    # 权限不足
    TIMEOUT = "timeout"    # 执行超时
    ERROR = "error"    # 其他运行错误

@dataclass
class ToolResult:
    """工具执行的统一结果对象: 成败都以本对象返回"""
    call_id:str    # 对应的工具调用ID
    tool_name:str    # 工具名
    status:ToolStatus    # 执行终态
    data: Any = None    # 成功时的返回值
    error_code: str | None = None    # 失败时的错误码
    error_message: str | None = None    # 失败时的错误信息
    attempts: int = 1    # 实际尝试次数

    @property
    def ok(self) -> bool:
        """是否成功(status 为 SUCCESS)"""
        return self.status == ToolStatus.SUCCESS
    
    def to_model_output(self)->str:
        """序列化为 JSON 字符串，作为工具结果回传给模型(无参数)"""
        return json.dumps(asdict(self) , ensure_ascii=False ,default=str)
    


