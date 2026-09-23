from dataclasses import dataclass, field
from enum import StrEnum


class MCPTransport(StrEnum):
    HTTP = "http"
    STDIO = "stdio"

@dataclass(frozen=True)
class MCPToolPolicy:
    """Harness 可信的的 Tool Policy"""
    side_effect: bool = False
    idempotent: bool = False
    requires_approval: bool = False
    max_retries: int = 0
    timeout_seconds: float = 20.0

# 远端工具的能力声明不被信任。运行期由前端登记的 Server（以及重启后从库里恢复的那些）
# 在用户逐个声明策略之前，一律按「有副作用 + 需要人工批准」处理——宁可多一次审批，
# 也不要把一个未知远端工具的调用当作只读操作静默执行。
UNTRUSTED_TOOL_POLICY = MCPToolPolicy(
    side_effect=True,
    requires_approval=True,
)

@dataclass(frozen=True)
class MCPServerConfig:
    """MCPServer 配置"""
    name: str
    transport: MCPTransport
    url: str | None = None
    command: str | None = None
    args: tuple[str , ...] = ()
    env: dict[str , str] = field(default_factory=dict)
    enabled: bool = True
    required : bool = False
    tool_prefix: str | None = None
    allowed_tools: frozenset[str] | None = None
    tool_policies: dict[str, MCPToolPolicy] = field(default_factory=dict)
    # 未在 tool_policies 里逐个声明的远端工具使用这条默认策略。
    # 远端工具的能力声明不被信任，因此运行期由前端登记的 Server 会传入更保守的默认值
    # （side_effect=True + requires_approval=True），而不是这个只读默认。
    default_tool_policy: MCPToolPolicy = field(
        default_factory=MCPToolPolicy
    )







