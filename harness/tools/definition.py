# 文件：harness/tools/definition.py
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

ToolHandler = (
    Callable[..., Any]
    | Callable[..., Awaitable[Any]]
)

@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    timeout_seconds: float = 10.0
    max_retries: int = 0
    required_permissions: frozenset[str] = field(
        default_factory=frozenset
    )
    side_effect: bool = False

    # Phase 10：是否允许“同一语义请求”安全重试。
    idempotent: bool = False

    # Phase 9：即使 side_effect=False，也可由业务明确要求审批。
    requires_approval: bool = False

    source: str = "local"
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
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
    run_id: str
    user_id: str | None = None
    tenant_id: str | None = None
    permissions: frozenset[str] = field(
        default_factory=frozenset
    )
    workspace_id: str | None = None
    # 工作区「绑定目录」的绝对路径与知识库目录：由服务端在提交 Run 时解析一次，
    # 这样工具只需要一个纯上下文，不必回头去问数据库或服务对象。
    workspace_path: str | None = None
    knowledge_path: str | None = None
    # 本次 Run 可用工具的冻结快照。AgentRunner 在 create_execution 时写入，
    # 之后既用于筛选发给模型的 schema，也用于执行前的准入判断——因此运行期
    # 新增（例如前端登记的 MCP Server）不会改变已经在跑的 Run 的能力集合。
    # None 表示“不限制”，用于不经过 Runner 的直接调用（测试与旧调用方）。
    tool_names: frozenset[str] | None = None
