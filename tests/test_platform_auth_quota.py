# 文件：tests/test_platform_auth_quota.py
from datetime import UTC, datetime

import pytest

from harness.persistence.database import Database
from harness.platform import (
    ApiKeyManager,
    BillingService,
    QuotaService,
    SQLitePlatformStore,
    UsageMetric,
    seed_default_plans,
)
from harness.platform.errors import AuthenticationError
from harness.platform.models import TenantStatus
from harness.platform.quota import utc_month_window


def build_store(tmp_path):
    database = Database(str(tmp_path / "platform.db"))
    database.initialize()
    store = SQLitePlatformStore(database)
    store.initialize()
    seed_default_plans(store)
    return database, store


def test_api_key_only_stores_digest_and_revoke_works(tmp_path) -> None:
    _, store = build_store(tmp_path)
    store.create_tenant(
        tenant_id="tenant_a",
        name="Tenant A",
        plan_id="starter_v1",
    )
    manager = ApiKeyManager(
        store=store,
        pepper="test-pepper-at-least-16-chars",
    )
    issued = manager.create_key(
        tenant_id="tenant_a",
        name="ci",
        scopes=frozenset({"runs:create"}),
    )
    record = store.get_api_key(issued.record.id)
    assert record is not None
    assert issued.secret not in record.key_hash

    principal = manager.authenticate(issued.secret)
    assert principal.tenant_id == "tenant_a"

    store.revoke_api_key(record.id)
    with pytest.raises(AuthenticationError):
        manager.authenticate(issued.secret)


def test_monthly_token_quota_blocks_new_run(tmp_path) -> None:
    _, store = build_store(tmp_path)
    tenant = store.create_tenant(
        tenant_id="tenant_q",
        name="Quota Tenant",
        plan_id="starter_v1",
    )
    plan = store.get_plan("starter_v1")
    assert plan is not None

    quota = QuotaService(store)
    assert quota.check_run_submission(tenant=tenant, plan=plan).allowed

    store.record_usage(
        event_key="quota:input",
        tenant_id=tenant.id,
        plan_id=plan.id,
        metric=UsageMetric.INPUT_TOKENS,
        quantity=plan.limits.max_input_tokens_per_month,
        run_id=None,
        metadata={},
    )
    decision = quota.check_run_submission(tenant=tenant, plan=plan)
    assert decision.allowed is False
    assert decision.code == "QUOTA_INPUT_TOKENS_EXCEEDED"


def test_billing_uses_immutable_usage_ledger(tmp_path) -> None:
    _, store = build_store(tmp_path)
    tenant = store.create_tenant(
        tenant_id="tenant_bill",
        name="Billing Tenant",
        plan_id="starter_v1",
    )
    plan = store.get_plan("starter_v1")
    assert plan is not None

    # Starter 内含 500k input tokens；多用 1000 token 会产生一条费用。
    store.record_usage(
        event_key="billing:input",
        tenant_id=tenant.id,
        plan_id=plan.id,
        metric=UsageMetric.INPUT_TOKENS,
        quantity=501_000,
        run_id=None,
        metadata={},
    )
    start, end = utc_month_window()
    preview = BillingService(store=store).preview(
        tenant_id=tenant.id,
        start=start,
        end=end,
    )
    assert preview.total_microusd == 1_000
    assert preview.lines[0].billable_units == 1_000
