# 文件：harness/tools/idempotency.py
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from harness.tools.result import ToolResult

class IdempotencyStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    UNCERTAIN = "uncertain"

@dataclass(frozen=True)
class IdempotencyRecord:
    idempotency_key: str
    payload_hash: str
    status: IdempotencyStatus
    acquired: bool
    result: ToolResult | None = None
    external_operation_id: str | None = None
    error_message: str | None = None

class IdempotencyStore(Protocol):
    def begin(
        self,
        *,
        idempotency_key: str,
        run_id: str,
        call_id: str,
        tool_name: str,
        payload_hash: str,
    ) -> IdempotencyRecord:
        ...

    def complete(
        self,
        *,
        idempotency_key: str,
        result: ToolResult,
        external_operation_id: str | None = None,
    ) -> None:
        ...

    def mark_uncertain(
        self,
        *,
        idempotency_key: str,
        error_message: str,
    ) -> None:
        ...
