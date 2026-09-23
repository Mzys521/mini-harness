# 文件：harness/app/runtime.py
from dataclasses import dataclass
from typing import Any


@dataclass
class RuntimeBundle:
    """高级用户可访问底层组件；普通用户只需要 HarnessApp。"""
    application: Any
    durable: Any
    worker_pool: Any
    observability: Any
    metrics: Any
    security: Any
    database: Any
    durable_store: Any
    registry: Any
    model: Any
    platform: Any = None
    desktop: Any = None
    events: Any = None
    # 多 RAG 仓库（KnowledgeRepositoryCatalog）；未启用 [rag] 时为 None。
    knowledge: Any = None
    # 运行期 MCP：MCPManager 与它背后的 Server 清单存储；未启用 [mcp] 时为 None。
    mcp: Any = None
    mcp_store: Any = None
    personal: Any = None
    scheduler: Any = None
    temporary: Any = None
