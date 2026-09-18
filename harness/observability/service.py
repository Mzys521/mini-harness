from contextlib import contextmanager
from typing import Any , Iterator

from opentelemetry import trace , metrics
from opentelemetry.trace import Status , StatusCode


class SpanHandle:
    """限制核心业务真正需要的 Span 能力"""

    def __init__(self, span) -> None:
        self._span = span

    def set_attribute(self , key : str , value ) -> None:
        if value is not None:
            self._span.set_attribute(key , value)
    
    def add_event(self , name: str , attributes : dict[str , Any] | None = None) -> None:
        self._span.add_event(name, attributes = attributes)

    def record_exception(self , exc : BaseException) -> None:
        self._span.record_exception(exc)

    def set_error(self , description: str) -> None:
        self._span.set_status(Status(StatusCode.ERROR , description))

class Observability:
    def __init__(self , intrumentation_name: str = "mini-harness") -> None:
        self.tracer = trace.get_tracer(intrumentation_name)
        self.meter = metrics.get_meter(intrumentation_name)

    @contextmanager  # pyright: ignore[reportDeprecated, reportDeprecated]
    def span(self, name: str , attributes : dict[str , Any] | None = None) -> Iterator[SpanHandle]:
        with self.tracer.start_as_current_span(name , attributes = attributes or {}) as span:
            handle = SpanHandle(span)
            try: 
                yield handle
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR , str(exc)))
                raise
    
    

    

