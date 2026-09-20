# 文件：harness/durable/tracing.py
from contextlib import contextmanager

from opentelemetry import (
    context,
    propagate,
)

def inject_current_context() -> dict[str, str]:
    """把当前 OpenTelemetry Context 序列化成可持久化 Carrier。"""
    carrier: dict[str, str] = {}
    propagate.inject(
        carrier
    )
    return carrier

@contextmanager
def use_trace_carrier(
    carrier: dict[str, str] | None,
):
    """在另一个 Worker/进程恢复 W3C Trace Context。"""
    extracted = propagate.extract(
        carrier or {}
    )
    token = context.attach(
        extracted
    )
    try:
        yield
    finally:
        context.detach(
            token
        )
