from dataclasses import dataclass , field
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







