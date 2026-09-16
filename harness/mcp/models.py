from dataclasses import dataclass , field
from typing import Any

@dataclass(frozen=True)
class MCPToolSpec:
    """SDK 对象在 Integration Boundary 被装换成内部模型"""
    server_name : str
    remote_name : str
    local_name : str
    description : str
    input_schema : dict[str, Any]
    annotations : dict[str, Any] = field(default_factory=dict)




















