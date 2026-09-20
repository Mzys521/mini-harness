# 文件：tests/test_platform_metering.py
from types import SimpleNamespace

from harness.durable.models import DurableRunStatus
from harness.models import ModelUsage, RunEvidence, ToolExecutionRecord
from harness.persistence.database import Database
from harness.platform import SQLitePlatformStore, UsageMetric, UsageReconciler, seed_default_plans
from harness.state.models import Conversation, Run, RunStatus


class FakeDurableStore:
    def __init__(self, record):
        self.record = record

    def get(self, run_id):
        return self.record if run_id == "run_meter" else None


def test_usage_reconciler_is_idempotent(tmp_path) -> None:
    database = Database(str(tmp_path / "metering.db"))
    database.initialize()
    store = SQLitePlatformStore(database)
    store.initialize()
    seed_default_plans(store)
    store.create_tenant(
        tenant_id="tenant_meter",
        name="Meter",
        plan_id="starter_v1",
    )

    conversation = Conversation(
        id="conv_meter",
        user_id="user",
        tenant_id="tenant_meter",
    )
    run = Run(
        id="run_meter",
        conversation_id=conversation.id,
        status=RunStatus.COMPLETED,
    )
    with database.uow() as uow:
        uow.conversations.add(conversation)
        uow.runs.add(run)
        uow.commit()
    store.bind_run_account(
        run_id=run.id,
        tenant_id="tenant_meter",
        plan_id="starter_v1",
    )

    evidence = RunEvidence(
        tool_executions=[
            ToolExecutionRecord(
                call_id="call_1",
                name="add",
                arguments={"a": 1, "b": 2},
                status="success",
            )
        ],
        model_usage=ModelUsage(
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
        ),
    )
    record = SimpleNamespace(
        status=DurableRunStatus.COMPLETED,
        execution=SimpleNamespace(evidence=evidence),
    )
    reconciler = UsageReconciler(
        platform_store=store,
        durable_store=FakeDurableStore(record),
    )

    assert reconciler.sync_once() == 1
    assert reconciler.sync_once() == 0

    # 只应该出现一次，不因 Reconciler 重试而重复计量。
    from harness.platform.quota import utc_month_window
    start, end = utc_month_window()
    assert store.sum_usage(
        tenant_id="tenant_meter",
        metric=UsageMetric.INPUT_TOKENS,
        start=start,
        end=end,
    ) == 100
