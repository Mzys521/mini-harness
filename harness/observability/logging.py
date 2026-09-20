import json
import logging
from datetime import UTC , datetime
from pathlib import Path
from opentelemetry import trace

_STANDARD_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process",
}

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": format(span_context.trace_id, "032x") if span_context.is_valid else None,
            "span_id": format(span_context.span_id, "016x") if span_context.is_valid else None,
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_FIELDS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)

def configure_structured_logging(level: str = "INFO", path: str | None = None) -> None:
    """配置结构化 JSON 日志。

    参数 level: 日志级别
    参数 path: 为 None 时输出到控制台；否则以 UTF-8 追加写入该文件
    """
    if path is None:
        handler: logging.Handler = logging.StreamHandler()
    else:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(target, encoding="utf-8")

    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
