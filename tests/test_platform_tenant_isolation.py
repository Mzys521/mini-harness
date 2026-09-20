# 文件：tests/test_platform_tenant_isolation.py
import pytest

from harness.durable.models import DurableResult, DurableRunStatus
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
from harness.platform.errors import ResourceNotFoundError
from harness.platform.models import Principal
from harness.state.models import Conversation, Run


class FakeDurable:
    def get_result(self, run_id: str):
        return DurableResult(
            conversation_id="conv_a",
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


def test_run_object_level_authorization_hides_other_tenant(tmp_path) -> None:
    database = Database(str(tmp_path / "isolation.db"))
    database.initialize()
    store = SQLitePlatformStore(database)
    store.initialize()
    seed_default_plans(store)
    store.create_tenant(
        tenant_id="tenant_a",
        name="A",
        plan_id="starter_v1",
    )
    store.create_tenant(
        tenant_id="tenant_b",
        name="B",
        plan_id="starter_v1",
    )

    with database.uow() as uow:
        uow.conversations.add(
            Conversation(
                id="conv_a",
                user_id="user_a",
                tenant_id="tenant_a",
            )
        )
        uow.runs.add(
            Run(
                id="run_a",
                conversation_id="conv_a",
            )
        )
        uow.commit()

    api_keys = ApiKeyManager(
        store=store,
        pepper="test-pepper-at-least-16-chars",
    )
    service = CommercialPlatformService(
        durable=FakeDurable(),
        durable_store=FakeDurableStore(),
        store=store,
        quota=QuotaService(store),
        metering=UsageReconciler(
            platform_store=store,
            durable_store=FakeDurableStore(),
        ),
        billing=BillingService(store=store),
        api_keys=api_keys,
    )

    principal_b = Principal(
        tenant_id="tenant_b",
        api_key_id="key_b",
        scopes=frozenset({"runs:read"}),
    )
    with pytest.raises(ResourceNotFoundError):
        service.get_run(principal=principal_b, run_id="run_a")
