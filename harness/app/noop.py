# 文件：harness/app/noop.py
from contextlib import contextmanager


class _NoopSpan:
    def set_attribute(self, key, value) -> None:
        return None

    def add_event(self, name, attributes=None) -> None:
        return None

    def record_exception(self, exc) -> None:
        return None

    def set_error(self, description) -> None:
        return None


class _NoopInstrument:
    def add(self, value, attributes=None) -> None:
        return None

    def record(self, value, attributes=None) -> None:
        return None


class _NoopMeter:
    def create_counter(self, *args, **kwargs):
        return _NoopInstrument()

    def create_histogram(self, *args, **kwargs):
        return _NoopInstrument()


class NoopObservability:
    """默认不开启 Exporter 时仍保持所有内部调用接口稳定。"""
    def __init__(self) -> None:
        self.meter = _NoopMeter()

    @contextmanager
    def span(self, name, attributes=None):
        yield _NoopSpan()


class NoopMetrics:
    """通过动态属性减少 Core 对具体 Metric 集合的依赖。"""
    def __getattr__(self, name):
        return _NoopInstrument()


class NoopSecurityService:
    """仅用于显式关闭安全能力的开发场景；生产默认不应关闭。"""
    def inspect_input(self, *, text: str, run_id: str):
        return text, []

    def inspect_output(self, *, text: str, run_id: str):
        return text, []

    def inspect_tool_result(self, *, text: str, run_id: str, tool_name: str):
        return text, []

    def authorize_tool(self, *, tool, call, context):
        from harness.security.models import SecurityAction, SecurityDecision

        return SecurityDecision(
            action=SecurityAction.ALLOW,
            code="SEC_DISABLED",
            reason="Security explicitly disabled by application config.",
        )

    def finish_run(self, run_id: str) -> None:
        return None
