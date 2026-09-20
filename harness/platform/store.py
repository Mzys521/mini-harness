# 文件：harness/platform/store.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from harness.persistence.database import Database, dump_json, load_json
from harness.platform.models import (
    ApiKeyRecord,
    ApiKeyStatus,
    MeterRate,
    Plan,
    PlanLimits,
    Tenant,
    TenantStatus,
    UsageEvent,
    UsageMetric,
    UsageSummary,
    utc_now,
)
from harness.platform.schema import PLATFORM_SCHEMA_SQL
from harness.state.ids import new_id


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


class SQLitePlatformStore:
    """Commercial Platform 的 SQLite Adapter。

    这里故意不把平台 SQL 塞进 Phase 4 Repository：业务运行态与商业控制面
    虽然共享一个 Database 连接工厂，但保持独立 Schema / Store 边界。
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def initialize(self) -> None:
        connection = self.database.connect()
        try:
            connection.executescript(PLATFORM_SCHEMA_SQL)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_plan(self, plan: Plan) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO platform_plans (
                    id, name, limits_json, tool_permissions_json,
                    rates_json, active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.id,
                    plan.name,
                    dump_json({
                        "max_concurrent_runs": plan.limits.max_concurrent_runs,
                        "max_runs_per_day": plan.limits.max_runs_per_day,
                        "max_input_tokens_per_month": plan.limits.max_input_tokens_per_month,
                        "max_output_tokens_per_month": plan.limits.max_output_tokens_per_month,
                        "max_tool_calls_per_month": plan.limits.max_tool_calls_per_month,
                    }),
                    dump_json(sorted(plan.tool_permissions)),
                    dump_json([
                        {
                            "metric": rate.metric.value,
                            "unit_size": rate.unit_size,
                            "price_microusd": rate.price_microusd,
                            "included_units": rate.included_units,
                        }
                        for rate in plan.rates
                    ]),
                    1 if plan.active else 0,
                    utc_now().isoformat(),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_plan(self, plan: Plan) -> None:
        if self.get_plan(plan.id) is not None:
            return
        self.create_plan(plan)

    def get_plan(self, plan_id: str) -> Plan | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM platform_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
            return self._plan_from_row(row) if row else None
        finally:
            connection.close()

    def list_plans(self) -> list[Plan]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM platform_plans ORDER BY id"
            ).fetchall()
            return [self._plan_from_row(row) for row in rows]
        finally:
            connection.close()

    def create_tenant(
        self,
        *,
        tenant_id: str,
        name: str,
        plan_id: str,
        status: TenantStatus = TenantStatus.ACTIVE,
    ) -> Tenant:
        now = utc_now()
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO platform_tenants (
                    id, name, plan_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    name,
                    plan_id,
                    status.value,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.commit()
            return Tenant(
                id=tenant_id,
                name=name,
                plan_id=plan_id,
                status=status,
                created_at=now,
                updated_at=now,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM platform_tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
            return self._tenant_from_row(row) if row else None
        finally:
            connection.close()

    def list_tenants(self) -> list[Tenant]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM platform_tenants ORDER BY created_at"
            ).fetchall()
            return [self._tenant_from_row(row) for row in rows]
        finally:
            connection.close()

    def set_tenant_status(
        self,
        *,
        tenant_id: str,
        status: TenantStatus,
    ) -> None:
        connection = self.database.connect()
        try:
            cursor = connection.execute(
                """
                UPDATE platform_tenants
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    utc_now().isoformat(),
                    tenant_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"tenant not found: {tenant_id}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def set_tenant_plan(
        self,
        *,
        tenant_id: str,
        plan_id: str,
    ) -> None:
        connection = self.database.connect()
        try:
            cursor = connection.execute(
                """
                UPDATE platform_tenants
                SET plan_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    plan_id,
                    utc_now().isoformat(),
                    tenant_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"tenant not found: {tenant_id}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def insert_api_key(self, record: ApiKeyRecord) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO platform_api_keys (
                    id, tenant_id, name, key_hash, scopes_json,
                    status, created_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.tenant_id,
                    record.name,
                    record.key_hash,
                    dump_json(sorted(record.scopes)),
                    record.status.value,
                    record.created_at.isoformat(),
                    (
                        record.last_used_at.isoformat()
                        if record.last_used_at
                        else None
                    ),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_api_key(self, api_key_id: str) -> ApiKeyRecord | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM platform_api_keys WHERE id = ?",
                (api_key_id,),
            ).fetchone()
            return self._api_key_from_row(row) if row else None
        finally:
            connection.close()

    def touch_api_key(self, api_key_id: str) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                UPDATE platform_api_keys
                SET last_used_at = ?
                WHERE id = ?
                """,
                (utc_now().isoformat(), api_key_id),
            )
            connection.commit()
        finally:
            connection.close()

    def revoke_api_key(self, api_key_id: str) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                UPDATE platform_api_keys
                SET status = ?
                WHERE id = ?
                """,
                (ApiKeyStatus.REVOKED.value, api_key_id),
            )
            connection.commit()
        finally:
            connection.close()

    def record_audit(
        self,
        *,
        actor_api_key_id: str,
        tenant_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        metadata: dict | None = None,
    ) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO platform_audit_events (
                    id, actor_api_key_id, tenant_id, action,
                    target_type, target_id, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("paudit"),
                    actor_api_key_id,
                    tenant_id,
                    action,
                    target_type,
                    target_id,
                    dump_json(metadata or {}),
                    utc_now().isoformat(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def bind_run_account(
        self,
        *,
        run_id: str,
        tenant_id: str,
        plan_id: str,
    ) -> None:
        """冻结 Run 提交时的 Tenant / Plan，用于后续计量与计费。"""
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT OR IGNORE INTO platform_run_accounts (
                    run_id, tenant_id, plan_id, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    tenant_id,
                    plan_id,
                    utc_now().isoformat(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def record_usage(
        self,
        *,
        event_key: str,
        tenant_id: str,
        plan_id: str,
        metric: UsageMetric,
        quantity: int,
        run_id: str | None,
        metadata: dict | None = None,
        created_at: datetime | None = None,
    ) -> bool:
        """Idempotent usage write；event_key 已存在时返回 False。"""
        event_id = new_id("usage")
        created = created_at or utc_now()
        connection = self.database.connect()
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO platform_usage_events (
                    id, event_key, tenant_id, plan_id, metric,
                    quantity, run_id, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event_key,
                    tenant_id,
                    plan_id,
                    metric.value,
                    int(quantity),
                    run_id,
                    dump_json(metadata or {}),
                    created.isoformat(),
                ),
            )
            connection.commit()
            return cursor.rowcount == 1
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def sum_usage(
        self,
        *,
        tenant_id: str,
        metric: UsageMetric,
        start: datetime,
        end: datetime,
    ) -> int:
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) AS total
                FROM platform_usage_events
                WHERE tenant_id = ?
                  AND metric = ?
                  AND created_at >= ?
                  AND created_at < ?
                """,
                (
                    tenant_id,
                    metric.value,
                    start.isoformat(),
                    end.isoformat(),
                ),
            ).fetchone()
            return int(row["total"])
        finally:
            connection.close()

    def usage_summary(
        self,
        *,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> UsageSummary:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT metric, COALESCE(SUM(quantity), 0) AS total
                FROM platform_usage_events
                WHERE tenant_id = ?
                  AND created_at >= ?
                  AND created_at < ?
                GROUP BY metric
                """,
                (
                    tenant_id,
                    start.isoformat(),
                    end.isoformat(),
                ),
            ).fetchall()
            return UsageSummary(
                tenant_id=tenant_id,
                period_start=start,
                period_end=end,
                quantities={row["metric"]: int(row["total"]) for row in rows},
            )
        finally:
            connection.close()

    def usage_by_plan(
        self,
        *,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> dict[tuple[str, str], int]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT plan_id, metric, COALESCE(SUM(quantity), 0) AS total
                FROM platform_usage_events
                WHERE tenant_id = ?
                  AND created_at >= ?
                  AND created_at < ?
                GROUP BY plan_id, metric
                """,
                (
                    tenant_id,
                    start.isoformat(),
                    end.isoformat(),
                ),
            ).fetchall()
            return {
                (row["plan_id"], row["metric"]): int(row["total"])
                for row in rows
            }
        finally:
            connection.close()

    def count_active_runs(self, tenant_id: str) -> int:
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM runs r
                JOIN conversations c ON c.id = r.conversation_id
                WHERE c.tenant_id = ?
                  AND r.status IN ('pending', 'running', 'waiting')
                """,
                (tenant_id,),
            ).fetchone()
            return int(row["total"])
        finally:
            connection.close()

    def get_run_tenant_id(self, run_id: str) -> str | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT c.tenant_id
                FROM runs r
                JOIN conversations c ON c.id = r.conversation_id
                WHERE r.id = ?
                """,
                (run_id,),
            ).fetchone()
            return str(row["tenant_id"]) if row else None
        finally:
            connection.close()

    def get_unmetered_terminal_run(
        self,
        run_id: str,
    ) -> tuple[str, str, str] | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT r.id AS run_id, a.tenant_id, a.plan_id
                FROM runs r
                JOIN platform_run_accounts a ON a.run_id = r.id
                LEFT JOIN platform_metered_runs m ON m.run_id = r.id
                WHERE r.id = ?
                  AND r.status IN ('completed', 'failed', 'cancelled')
                  AND m.run_id IS NULL
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            return (
                str(row["run_id"]),
                str(row["tenant_id"]),
                str(row["plan_id"]),
            )
        finally:
            connection.close()

    def list_unmetered_terminal_runs(self, *, limit: int = 100) -> list[tuple[str, str, str]]:
        """返回 run_id / tenant_id / 当前 plan_id；event 写入后再 mark metered。"""
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT r.id AS run_id, a.tenant_id, a.plan_id
                FROM runs r
                JOIN platform_run_accounts a ON a.run_id = r.id
                LEFT JOIN platform_metered_runs m ON m.run_id = r.id
                WHERE r.status IN ('completed', 'failed', 'cancelled')
                  AND m.run_id IS NULL
                ORDER BY r.updated_at ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [
                (str(row["run_id"]), str(row["tenant_id"]), str(row["plan_id"]))
                for row in rows
            ]
        finally:
            connection.close()

    def mark_run_metered(self, *, run_id: str, tenant_id: str) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT OR IGNORE INTO platform_metered_runs (
                    run_id, tenant_id, metered_at
                ) VALUES (?, ?, ?)
                """,
                (run_id, tenant_id, utc_now().isoformat()),
            )
            connection.commit()
        finally:
            connection.close()

    def is_run_metered(self, run_id: str) -> bool:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT 1 FROM platform_metered_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    @staticmethod
    def _plan_from_row(row) -> Plan:
        limits_data = load_json(row["limits_json"])
        rates_data = load_json(row["rates_json"])
        return Plan(
            id=str(row["id"]),
            name=str(row["name"]),
            limits=PlanLimits(
                max_concurrent_runs=int(limits_data["max_concurrent_runs"]),
                max_runs_per_day=int(limits_data["max_runs_per_day"]),
                max_input_tokens_per_month=int(limits_data["max_input_tokens_per_month"]),
                max_output_tokens_per_month=int(limits_data["max_output_tokens_per_month"]),
                max_tool_calls_per_month=int(limits_data["max_tool_calls_per_month"]),
            ),
            tool_permissions=frozenset(load_json(row["tool_permissions_json"])),
            rates=tuple(
                MeterRate(
                    metric=UsageMetric(item["metric"]),
                    unit_size=int(item["unit_size"]),
                    price_microusd=int(item["price_microusd"]),
                    included_units=int(item.get("included_units", 0)),
                )
                for item in rates_data
            ),
            active=bool(row["active"]),
        )

    @staticmethod
    def _tenant_from_row(row) -> Tenant:
        return Tenant(
            id=str(row["id"]),
            name=str(row["name"]),
            plan_id=str(row["plan_id"]),
            status=TenantStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _api_key_from_row(row) -> ApiKeyRecord:
        return ApiKeyRecord(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            name=str(row["name"]),
            key_hash=str(row["key_hash"]),
            scopes=frozenset(load_json(row["scopes_json"])),
            status=ApiKeyStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_used_at=_parse_dt(row["last_used_at"]),
        )
