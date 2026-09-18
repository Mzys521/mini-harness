
from dataclasses import dataclass , field
from typing import Any , Callable , Awaitable

ToolHandler = Callable[... , Any] | Callable[... , Awaitable[Any]] # 工具处理函数类型: 接收关键字参数并返回执行结果

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
    side_effect : bool = False   # 是否有副作用(删除/写入等)
    source : str = "local"        # 工具来源
    metadata : dict[str , Any] = field(default_factory=dict)    # 元数据

    # 默认 False ， 因此 phase 1-7 普通 Tool 不受影响
    inject_context: bool = False

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
            "strict": True,
        }

@dataclass(frozen=True)
class ToolContext:
    """工具执行上下文(不可变): 携带运行/用户/权限信息"""
    run_id: str    # 本次运行唯一ID
    user_id: str | None = None    # 调用用户ID
    tenant_id: str | None = None    # 租户ID(多租户隔离)
    permissions: frozenset[str] = field(default_factory=frozenset) # 用户权限

