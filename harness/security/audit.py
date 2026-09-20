# 文件：harness/security/audit.py
import json
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from harness.security.models import (
    SecurityAuditEvent,
)

class NullAuditSink:
    def emit(
        self,
        event: SecurityAuditEvent,
    ) -> None:
        return None

class JsonlAuditSink:
    """开发基线：Append-only 风格 JSONL Security Audit。"""

    def __init__(
        self,
        path: str,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._lock = Lock()

    def emit(
        self,
        event: SecurityAuditEvent,
    ) -> None:
        payload = asdict(event)
        payload["created_at"] = (
            event.created_at.isoformat()
        )

        line = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )

        with self._lock:
            with self.path.open(
                "a",
                encoding="utf-8",
            ) as file:
                file.write(
                    line + "\n"
                )