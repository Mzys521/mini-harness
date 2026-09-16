
from dataclasses import dataclass , field
from typing import Any , Callable
from pydantic import BaseModel

ToolHandler = Callable[... , Any] # 工具处理函数类型: 接收关键字参数并返回执行结果

@dataclass(frozen=True)
class ToolContext:
    """工具执行上下文(不可变): 携带运行/用户/权限信息"""
    run_id: str    # 本次运行唯一ID
    user_id: str | None = None    # 调用用户ID
    tenant_id: str | None = None    # 租户ID(多租户隔离)
    permissions: frozenset[str] = field(default_factory=frozenset) # 用户权限

@dataclass(frozen=True)
class Tool:
    """Harness 内部唯一工具定义(不可变)"""
    name : str                    # 工具名
    description : str             # 工具说明
    input_schema : dict[str, Any] # 输入参数 schema
    handler : ToolHandler         # 工具处理函数
    timeout_seconds : float = 10.0    # 单次执行超时(秒)
    max_retries : int = 0         # 允许重试次数(仅对 RetryableToolError 生效)
    required_permissions : frozenset[str] = field(default_factory=frozenset)    # 调用所需权限
    side_effects : bool = False   # 是否有副作用(删除/写入等)
    source : str = "local"        # 工具来源
    metadata : dict[str , Any] = field(default_factory=dict)    # 元数据

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
            "strict": True,
        }


# 在 0.6.0 版本中，之前的Tool 类将被重写，取而代之的是崭新的统一工具类
# @dataclass(frozen=True)
# class Tool:
#     """工具的完整定义(不可变): 元信息 + 参数模型 + 执行入口"""
#     name: str    # 工具名(模型调用时使用)
#     description: str    # 工具说明(展示给模型)
#     args_model: type[BaseModel]    # 参数模型(pydantic): 校验参数并生成 schema
#     handler: ToolHandler    # 实际执行函数(同步或异步)
#     timeout_seconds: float = 10.0    # 单次执行超时(秒)
#     max_retries: int = 0    # 允许重试次数(仅对 RetryableToolError 生效)
#     required_permissions: frozenset[str] = field(default_factory=frozenset)    # 调用所需权限
#     side_effects: bool = False    # 是否有副作用(删除/写入等)

#     def to_openai_schema(self) -> dict[str, Any]:
#         """ 转换为 OpenAI 工具格式(返回 function 类型 schema，无参数) """
#         return{
#             "type": "function",
#             "name": self.name,
#             "description": self.description,
#             "parameters": self.args_model.model_json_schema(),
#             "strict": True,
#         }
