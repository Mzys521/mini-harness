# 文件：harness/durable/store.py
import json
from datetime import UTC, datetime, timedelta

from harness.durable.models import (
    AgentExecutionState,
    DurableConflictError,
    DurableLeaseLostError,
    DurableRunRecord,
    DurableRunStatus,
    ExecutionPhase,
)
from harness.durable.serialization import (
    execution_from_dict,
    execution_to_dict,
)
from harness.persistence.database import (
    dump_json,
    load_json,
)
from harness.state.ids import new_id
from harness.tools.idempotency import (
    IdempotencyRecord,
    IdempotencyStatus,
)
from harness.tools.result import (
    ToolResult,
)

def _utc_now() -> datetime:
    return datetime.now(UTC)

def _parse_datetime(
    value: str | None,
) -> datetime | None:
    return (
        datetime.fromisoformat(value)
        if value
        else None
    )

class SQLiteDurableStore:
    """SQLite Durable Queue + Lease + Execution State Store。"""

    def __init__(self, database) -> None:
        self.database = database

    def enqueue(
        self,
        *,
        run_id: str,
        execution: AgentExecutionState,
        trace_carrier: dict[str, str] | None = None,
        available_at: datetime | None = None,
    ) -> None:
        now = _utc_now()
        available = (
            available_at
            or now
        )
        connection = (
            self.database.connect()
        )
        try:
            connection.execute(
                """
                INSERT INTO durable_runs (
                    run_id, execution_json, status, version,
                    lease_owner, lease_expires_at, available_at,
                    cancel_requested, trace_carrier_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 0, NULL, NULL, ?, 0, ?, ?, ?)
                """,
                (
                    run_id,
                    dump_json(
                        execution_to_dict(
                            execution
                        )
                    ),
                    DurableRunStatus.PENDING.value,
                    available.isoformat(),
                    dump_json(
                        trace_carrier
                        or {}
                    ),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            self._append_event(
                connection,
                run_id=run_id,
                event_type="durable.enqueued",
                payload={
                    "phase": execution.phase.value
                },
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(
        self,
        run_id: str,
    ) -> DurableRunRecord | None:
        connection = (
            self.database.connect()
        )
        try:
            row = connection.execute(
                """
                SELECT *
                FROM durable_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

            return (
                self._record_from_row(
                    row
                )
                if row
                else None
            )
        finally:
            connection.close()

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: float,
    ) -> DurableRunRecord | None:
        now = _utc_now()
        lease_expires = (
            now
            + timedelta(
                seconds=lease_seconds
            )
        )

        connection = (
            self.database.connect()
        )

        try:
            # SQLite 单写者语义下，BEGIN IMMEDIATE 让“选中 + claim”
            # 发生在同一个写事务中，避免两个 Worker 同时拿到同一 Run。
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT *
                FROM durable_runs
                WHERE
                    (status IN (?, ?) OR (status = 'waiting' AND cancel_requested = 1))
                    AND available_at <= ?
                    AND (
                        lease_owner IS NULL
                        OR lease_expires_at IS NULL
                        OR lease_expires_at <= ?
                    )
                ORDER BY available_at ASC, created_at ASC
                LIMIT 1
                """,
                (
                    DurableRunStatus.PENDING.value,
                    DurableRunStatus.RUNNING.value,
                    now.isoformat(),
                    now.isoformat(),
                ),
            ).fetchone()

            if row is None:
                connection.commit()
                return None

            current_version = int(
                row["version"]
            )

            cursor = connection.execute(
                """
                UPDATE durable_runs
                SET
                    status = ?,
                    lease_owner = ?,
                    lease_expires_at = ?,
                    version = version + 1,
                    updated_at = ?
                WHERE
                    run_id = ?
                    AND version = ?
                    AND (
                        lease_owner IS NULL
                        OR lease_expires_at IS NULL
                        OR lease_expires_at <= ?
                    )
                """,
                (
                    DurableRunStatus.RUNNING.value,
                    worker_id,
                    lease_expires.isoformat(),
                    now.isoformat(),
                    row["run_id"],
                    current_version,
                    now.isoformat(),
                ),
            )

            if cursor.rowcount != 1:
                connection.rollback()
                return None

            claimed = connection.execute(
                """
                SELECT *
                FROM durable_runs
                WHERE run_id = ?
                """,
                (row["run_id"],),
            ).fetchone()

            self._append_event(
                connection,
                run_id=row["run_id"],
                event_type="durable.claimed",
                payload={
                    "worker_id": worker_id,
                    "lease_expires_at": (
                        lease_expires.isoformat()
                    ),
                },
            )
            connection.commit()

            return self._record_from_row(
                claimed
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def heartbeat(
        self,
        *,
        run_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> None:
        connection = (
            self.database.connect()
        )
        try:
            expires = (
                _utc_now()
                + timedelta(
                    seconds=lease_seconds
                )
            )
            cursor = connection.execute(
                """
                UPDATE durable_runs
                SET
                    lease_expires_at = ?,
                    updated_at = ?
                WHERE
                    run_id = ?
                    AND lease_owner = ?
                    AND status = ?
                """,
                (
                    expires.isoformat(),
                    _utc_now().isoformat(),
                    run_id,
                    worker_id,
                    DurableRunStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise DurableLeaseLostError(
                    f"lease lost: run={run_id}"
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_claimed(
        self,
        *,
        run_id: str,
        worker_id: str,
        expected_version: int,
        execution: AgentExecutionState,
        status: DurableRunStatus,
        trace_carrier: dict[str, str],
        release_lease: bool,
        lease_seconds: float = 60.0,
        available_at: datetime | None = None,
    ) -> int:
        now = _utc_now()
        next_available = (
            available_at
            or now
        )
        connection = (
            self.database.connect()
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            cursor = connection.execute(
                """
                UPDATE durable_runs
                SET
                    execution_json = ?,
                    status = ?,
                    version = version + 1,
                    lease_owner = ?,
                    lease_expires_at = ?,
                    available_at = ?,
                    trace_carrier_json = ?,
                    updated_at = ?
                WHERE
                    run_id = ?
                    AND version = ?
                    AND lease_owner = ?
                """,
                (
                    dump_json(
                        execution_to_dict(
                            execution
                        )
                    ),
                    status.value,
                    (
                        None
                        if release_lease
                        else worker_id
                    ),
                    (
                        None
                        if release_lease
                        else (
                            now
                            + timedelta(
                                seconds=lease_seconds
                            )
                        ).isoformat()
                    ),
                    next_available.isoformat(),
                    dump_json(
                        trace_carrier
                    ),
                    now.isoformat(),
                    run_id,
                    expected_version,
                    worker_id,
                ),
            )

            if cursor.rowcount != 1:
                connection.rollback()
                raise DurableConflictError(
                    "durable state changed by "
                    "another worker: "
                    f"run={run_id}"
                )

            new_version_row = (
                connection.execute(
                    """
                    SELECT version
                    FROM durable_runs
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchone()
            )

            self._append_event(
                connection,
                run_id=run_id,
                event_type="durable.state_saved",
                payload={
                    "status": status.value,
                    "phase": execution.phase.value,
                    "worker_id": worker_id,
                },
            )

            connection.commit()

            return int(
                new_version_row[
                    "version"
                ]
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def release_for_retry(
        self,
        *,
        run_id: str,
        worker_id: str,
        expected_version: int,
        execution: AgentExecutionState,
        delay_seconds: float,
        trace_carrier: dict[str, str],
    ) -> int:
        return self.save_claimed(
            run_id=run_id,
            worker_id=worker_id,
            expected_version=expected_version,
            execution=execution,
            status=DurableRunStatus.PENDING,
            trace_carrier=trace_carrier,
            release_lease=True,
            lease_seconds=60.0,
            available_at=(
                _utc_now()
                + timedelta(
                    seconds=delay_seconds
                )
            ),
        )

    def wake_after_approval(
        self,
        *,
        run_id: str,
    ) -> None:
        connection = (
            self.database.connect()
        )
        now = _utc_now()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT *
                FROM durable_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    f"durable run not found: {run_id}"
                )

            state = execution_from_dict(
                load_json(
                    row["execution_json"]
                )
            )

            if (
                state.phase
                != ExecutionPhase.WAITING_APPROVAL
            ):
                # approve 本身是幂等的；如果已经被唤醒，不重复破坏状态。
                connection.commit()
                return

            state.phase = (
                ExecutionPhase.TOOL
            )

            connection.execute(
                """
                UPDATE durable_runs
                SET
                    execution_json = ?,
                    status = ?,
                    version = version + 1,
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    available_at = ?,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    dump_json(
                        execution_to_dict(
                            state
                        )
                    ),
                    DurableRunStatus.PENDING.value,
                    now.isoformat(),
                    now.isoformat(),
                    run_id,
                ),
            )

            self._append_event(
                connection,
                run_id=run_id,
                event_type="durable.woken_after_approval",
                payload={},
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def request_cancel(
        self,
        *,
        run_id: str,
    ) -> None:
        connection = (
            self.database.connect()
        )
        now = _utc_now()

        try:
            cursor = connection.execute(
                """
                UPDATE durable_runs
                SET
                    cancel_requested = 1,
                    available_at = ?,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    now.isoformat(),
                    now.isoformat(),
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(
                    f"durable run not found: {run_id}"
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


    def is_cancel_requested(
        self,
        run_id: str,
    ) -> bool:
        connection = (
            self.database.connect()
        )
        try:
            row = connection.execute(
                """
                SELECT cancel_requested
                FROM durable_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"durable run not found: {run_id}"
                )
            return bool(
                row["cancel_requested"]
            )
        finally:
            connection.close()

    def _record_from_row(
        self,
        row,
    ) -> DurableRunRecord:
        return DurableRunRecord(
            run_id=row["run_id"],
            status=DurableRunStatus(
                row["status"]
            ),
            version=int(
                row["version"]
            ),
            execution=execution_from_dict(
                load_json(
                    row["execution_json"]
                )
            ),
            lease_owner=row[
                "lease_owner"
            ],
            lease_expires_at=_parse_datetime(
                row[
                    "lease_expires_at"
                ]
            ),
            available_at=datetime.fromisoformat(
                row["available_at"]
            ),
            cancel_requested=bool(
                row["cancel_requested"]
            ),
            trace_carrier=load_json(
                row[
                    "trace_carrier_json"
                ]
            ),
            created_at=datetime.fromisoformat(
                row["created_at"]
            ),
            updated_at=datetime.fromisoformat(
                row["updated_at"]
            ),
        )

    @staticmethod
    def _append_event(
        connection,
        *,
        run_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        connection.execute(
            """
            INSERT INTO events (
                id, run_id, step_id,
                event_type, payload_json, created_at
            ) VALUES (?, ?, NULL, ?, ?, ?)
            """,
            (
                new_id("evt"),
                run_id,
                event_type,
                dump_json(payload),
                _utc_now().isoformat(),
            ),
        )

class SQLiteApprovalStore:
    """Phase 9 Approval Protocol 的 SQLite Durable 实现。"""

    def __init__(self, database) -> None:
        self.database = database

    def approve(
        self,
        *,
        run_id: str,
        call_id: str,
        tool_name: str,
        approved_by: str | None = None,
    ) -> None:
        now = _utc_now()
        connection = (
            self.database.connect()
        )

        try:
            connection.execute(
                """
                INSERT INTO durable_approvals (
                    run_id, call_id, tool_name, status,
                    approved_by, created_at, approved_at
                ) VALUES (?, ?, ?, 'approved', ?, ?, ?)
                ON CONFLICT(run_id, call_id, tool_name)
                DO UPDATE SET
                    status = 'approved',
                    approved_by = excluded.approved_by,
                    approved_at = excluded.approved_at
                """,
                (
                    run_id,
                    call_id,
                    tool_name,
                    approved_by,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def is_approved(
        self,
        *,
        run_id: str,
        call_id: str,
        tool_name: str,
    ) -> bool:
        connection = (
            self.database.connect()
        )

        try:
            row = connection.execute(
                """
                SELECT status
                FROM durable_approvals
                WHERE
                    run_id = ?
                    AND call_id = ?
                    AND tool_name = ?
                """,
                (
                    run_id,
                    call_id,
                    tool_name,
                ),
            ).fetchone()

            return (
                row is not None
                and row["status"]
                == "approved"
            )
        finally:
            connection.close()

class SQLiteRunBudgetStore:
    """同一个 call_id Resume 时不重复消耗 Tool Budget。"""

    def __init__(self, database) -> None:
        self.database = database

    def consume(self, *, run_id: str, limit: int | None = None, key: str | None = None) -> bool:
        """Legacy API retained for callers; personal runs have no call budget."""
        return True

    def clear(
        self,
        run_id: str,
    ) -> None:
        connection = (
            self.database.connect()
        )
        try:
            connection.execute(
                """
                DELETE FROM durable_run_budget_calls
                WHERE run_id = ?
                """,
                (run_id,),
            )
            connection.commit()
        finally:
            connection.close()

class SQLiteIdempotencyStore:
    """Tool Side Effect 的持久 Idempotency / Uncertain State 记录。"""

    def __init__(self, database) -> None:
        self.database = database

    def begin(
        self,
        *,
        idempotency_key: str,
        run_id: str,
        call_id: str,
        tool_name: str,
        payload_hash: str,
    ) -> IdempotencyRecord:
        now = _utc_now()
        connection = (
            self.database.connect()
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT *
                FROM tool_idempotency
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if row is None:
                connection.execute(
                    """
                    INSERT INTO tool_idempotency (
                        idempotency_key, run_id, call_id,
                        tool_name, payload_hash, status,
                        result_json, external_operation_id,
                        error_message, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
                    """,
                    (
                        idempotency_key,
                        run_id,
                        call_id,
                        tool_name,
                        payload_hash,
                        IdempotencyStatus.STARTED.value,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                connection.commit()

                return IdempotencyRecord(
                    idempotency_key=idempotency_key,
                    payload_hash=payload_hash,
                    status=IdempotencyStatus.STARTED,
                    acquired=True,
                )

            connection.commit()
            return self._record_from_row(
                row,
                acquired=False,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def complete(
        self,
        *,
        idempotency_key: str,
        result: ToolResult,
        external_operation_id: str | None = None,
    ) -> None:
        connection = (
            self.database.connect()
        )
        try:
            connection.execute(
                """
                UPDATE tool_idempotency
                SET
                    status = ?,
                    result_json = ?,
                    external_operation_id = ?,
                    error_message = NULL,
                    updated_at = ?
                WHERE idempotency_key = ?
                """,
                (
                    IdempotencyStatus.COMPLETED.value,
                    dump_json(
                        result.to_dict()
                    ),
                    external_operation_id,
                    _utc_now().isoformat(),
                    idempotency_key,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def mark_uncertain(
        self,
        *,
        idempotency_key: str,
        error_message: str,
    ) -> None:
        connection = (
            self.database.connect()
        )
        try:
            connection.execute(
                """
                UPDATE tool_idempotency
                SET
                    status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE idempotency_key = ?
                """,
                (
                    IdempotencyStatus.UNCERTAIN.value,
                    error_message,
                    _utc_now().isoformat(),
                    idempotency_key,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _record_from_row(
        row,
        *,
        acquired: bool,
    ) -> IdempotencyRecord:
        result = (
            ToolResult.from_dict(
                load_json(
                    row["result_json"]
                )
            )
            if row["result_json"]
            else None
        )

        return IdempotencyRecord(
            idempotency_key=row[
                "idempotency_key"
            ],
            payload_hash=row[
                "payload_hash"
            ],
            status=IdempotencyStatus(
                row["status"]
            ),
            acquired=acquired,
            result=result,
            external_operation_id=row[
                "external_operation_id"
            ],
            error_message=row[
                "error_message"
            ],
        )
