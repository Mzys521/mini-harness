# 文件：tests/test_platform_api.py
from dataclasses import dataclass

from fastapi.testclient import TestClient

from harness.durable.models import DurableResult, DurableRunStatus, DurableSubmission
from harness.persistence.database import Database
from harness.platform import (
    ApiKeyManager,
    BillingService,
    CommercialPlatformService,
    QuotaService,
    SQLitePlatformStore,
    UsageReconciler,
    seed_default_plans,
)
from harness.platform.api import create_app
from harness.platform.runtime import CommercialRuntime
from harness.state.models import Conversation, Run


class FakeDurable:
    async def submit(self, **kwargs):
        return DurableSubmission(
            conversation_id="conv_new",
            run_id="run_new",
            status=DurableRunStatus.PENDING,
        )

    def get_result(self, run_id):
        return DurableResult(
            conversation_id="conv_new",
            run_id=run_id,
            status=DurableRunStatus.PENDING,
            output=None,
        )

    def approve(self, **kwargs):
        return None

    def cancel(self, **kwargs):
        return None


class FakeDurableStore:
    def get(self, run_id):
        return None


@dataclass
class FakeCore:
    worker_pool: object = None


def test_api_uses_api_key_and_problem_details(tmp_path) -> None:
    database = Database(str(tmp_path / "api.db"))
    database.initialize()
    store = SQLitePlatformStore(database)
    store.initialize()
    seed_default_plans(store)
    store.create_tenant(
        tenant_id="tenant_api",
        name="API Tenant",
        plan_id="starter_v1",
    )
    keys = ApiKeyManager(
        store=store,
        pepper="test-pepper-at-least-16-chars",
    )
    issued = keys.create_key(
        tenant_id="tenant_api",
        name="client",
        scopes=frozenset({"runs:create", "runs:read"}),
    )
    durable = FakeDurable()
    fake_store = FakeDurableStore()
    metering = UsageReconciler(
        platform_store=store,
        durable_store=fake_store,
    )
    service = CommercialPlatformService(
        durable=durable,
        durable_store=fake_store,
        store=store,
        quota=QuotaService(store),
        metering=metering,
        billing=BillingService(store=store),
        api_keys=keys,
    )
    commercial = CommercialRuntime(
        core=FakeCore(),
        store=store,
        api_keys=keys,
        service=service,
        metering=metering,
        billing=BillingService(store=store),
    )
    app = create_app(commercial, start_background_workers=False)

    with TestClient(app) as client:
        unauthorized = client.get("/v1/me")
        assert unauthorized.status_code == 401
        assert unauthorized.headers["content-type"].startswith(
            "application/problem+json"
        )
        assert unauthorized.json()["code"] == "PLATFORM_AUTHENTICATION_FAILED"

        response = client.get(
            "/v1/me",
            headers={"X-API-Key": issued.secret},
        )
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "tenant_api"
