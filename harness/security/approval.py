# 文件：harness/security/approval.py
from dataclasses import dataclass
from threading import Lock

@dataclass(frozen=True)
class ApprovalKey:
    run_id: str
    call_id: str
    tool_name: str

class InMemoryApprovalStore:
    """Phase 9 兼容实现；Phase 10 Durable Runtime 使用 SQLiteApprovalStore。"""

    def __init__(self) -> None:
        self._approved: set[ApprovalKey] = set()
        self._lock = Lock()

    def approve(
        self,
        *,
        run_id: str,
        call_id: str,
        tool_name: str,
        approved_by: str | None = None,
    ) -> None:
        del approved_by
        key = ApprovalKey(
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
        )
        with self._lock:
            self._approved.add(key)

    def is_approved(
        self,
        *,
        run_id: str,
        call_id: str,
        tool_name: str,
    ) -> bool:
        key = ApprovalKey(
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
        )
        with self._lock:
            return key in self._approved

class InMemoryRunBudgetStore:
    """按 Tool Call ID 去重计数；同一 Durable Call Resume 不会重复消耗预算。"""

    def __init__(self) -> None:
        self._calls: dict[str, set[str]] = {}
        self._lock = Lock()

    def consume(
        self,
        *,
        run_id: str,
        limit: int,
        key: str | None = None,
    ) -> bool:
        budget_key = key or f"anonymous:{len(self._calls.get(run_id, set()))}"

        with self._lock:
            seen = self._calls.setdefault(
                run_id,
                set(),
            )

            if budget_key in seen:
                return True

            if len(seen) >= limit:
                return False

            seen.add(budget_key)
            return True

    def clear(
        self,
        run_id: str,
    ) -> None:
        with self._lock:
            self._calls.pop(
                run_id,
                None,
            )
