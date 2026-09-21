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
