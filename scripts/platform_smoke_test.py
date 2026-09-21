# 文件：scripts/platform_smoke_test.py
from pathlib import Path

from harness.persistence.database import Database
from harness.platform import (
    ApiKeyManager,
    BillingService,
    QuotaService,
    SQLitePlatformStore,
    UsageMetric,
    seed_default_plans,
)
from harness.platform.quota import utc_month_window


def main() -> None:
    db_path = Path("data/platform_smoke.db")
    if db_path.exists():
        db_path.unlink()

    database = Database(str(db_path))
    database.initialize()
    store = SQLitePlatformStore(database)
    store.initialize()
    seed_default_plans(store)

    tenant = store.create_tenant(
        tenant_id="tenant_smoke",
        name="Smoke Tenant",
        plan_id="starter_v1",
    )
    api_keys = ApiKeyManager(
        store=store,
        pepper="phase11-smoke-pepper-value",
    )
    issued = api_keys.create_key(
        tenant_id=tenant.id,
        name="smoke",
        scopes=frozenset({"runs:create", "usage:read", "billing:read"}),
    )
    principal = api_keys.authenticate(issued.secret)
    assert principal.tenant_id == tenant.id

    plan = store.get_plan(tenant.plan_id)
    assert plan is not None
    quota = QuotaService(store)
    assert quota.check_run_submission(tenant=tenant, plan=plan).allowed

    store.record_usage(
        event_key="smoke:input_tokens",
        tenant_id=tenant.id,
        plan_id=plan.id,
        metric=UsageMetric.INPUT_TOKENS,
        quantity=501_000,
        run_id=None,
        metadata={},
    )
    # 0.13 起配额退化为兼容门面：用量照常记账，但不再有上限会拒绝提交。
    decision = quota.check_run_submission(tenant=tenant, plan=plan)
    assert decision.allowed is True
    assert decision.code == "UNLIMITED"

    start, end = utc_month_window()
    preview = BillingService(store=store).preview(
        tenant_id=tenant.id,
        start=start,
        end=end,
    )
    assert preview.total_microusd == 1_000

    print("Platform Smoke Test 通过。")
    print("tenant:", tenant.id)
    print("quota:", decision.code)
    print("billing_microusd:", preview.total_microusd)


if __name__ == "__main__":
    main()
