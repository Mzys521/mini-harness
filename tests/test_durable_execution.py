# 文件：tests/test_durable_execution.py
import asyncio

import pytest
from pydantic import BaseModel, ConfigDict

from harness.context.budget import ApproxTokenCounter, TokenBudget
from harness.context.builder import ContextBuilder
from harness.context.policy import ContextPolicy
from harness.durable import (
    DurableAgentService,
    DurableConfig,
    DurableRunStatus,
    DurableWorker,
    DurableWorkerPool,
    SQLiteApprovalStore,
    SQLiteDurableStore,
    SQLiteIdempotencyStore,
    SQLiteRunBudgetStore,
)
from harness.models import (
    ModelResult,
    ModelUsage,
    ToolCall,
)
from harness.persistence.database import Database
from harness.runner import AgentRunner
from harness.security import (
    DefaultToolPolicy,
    InputLengthGuard,
    NullAuditSink,
    OutputLengthGuard,
    SecretOutputGuard,
    SecurityConfig,
    SecurityService,
)
from harness.tools.executor import ToolExecutor
from harness.tools.factory import tool_from_pydantic
from harness.tools.registry import ToolRegistry
from tests.fakes_security import (
    FakeObservability,
    FakeSecurityMetrics,
)

class WriteArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )
    value: str

class ScriptedModel:
    async def generate(
        self,
        *,
        input_data,
        tools,
        instructions=None,
        previous_response_id=None,
    ) -> ModelResult:
        del input_data, tools, instructions

        if previous_response_id is None:
            return ModelResult(
                tool_calls=[
                    ToolCall(
                        call_id="write_1",
                        name="write_value",
                        arguments={
                            "value": "hello"
                        },
                    )
                ],
                response_id="resp_1",
                usage=ModelUsage(
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                ),
            )

        return ModelResult(
            text="done",
            response_id="resp_2",
            usage=ModelUsage(
                input_tokens=5,
                output_tokens=3,
                total_tokens=8,
            ),
        )

def build_runtime(
    tmp_path,
):
    database = Database(
        str(
            tmp_path
            / "durable.db"
        )
    )
    database.initialize()

    observability = FakeObservability()
    metrics = FakeSecurityMetrics()

    approval_store = SQLiteApprovalStore(
        database
    )
    budget_store = SQLiteRunBudgetStore(
        database
    )
    idempotency_store = (
        SQLiteIdempotencyStore(
            database
        )
    )
    durable_store = SQLiteDurableStore(
        database
    )

    security = SecurityService(
        input_guards=[
            InputLengthGuard(
                10_000
            )
        ],
        output_guards=[
            SecretOutputGuard(),
            OutputLengthGuard(
                10_000
            ),
        ],
        tool_policy=DefaultToolPolicy(
            config=SecurityConfig(),
            approval_store=(
                approval_store
            ),
            budget_store=budget_store,
        ),
        audit_sink=NullAuditSink(),
        observability=observability,
        metrics=metrics,
    )

    calls: list[str] = []

    def write_value(
        value: str,
    ):
        calls.append(
            value
        )
        return {
            "written": value
        }

    registry = ToolRegistry()
    registry.register(
        tool_from_pydantic(
            name="write_value",
            description="测试副作用。",
            args_model=WriteArgs,
            handler=write_value,
            required_permissions=frozenset({
                "value.write"
            }),
            side_effect=True,
            idempotent=False,
        )
    )

    executor = ToolExecutor(
        registry,
        observability=observability,
        metrics=metrics,
        security=security,
        idempotency_store=(
            idempotency_store
        ),
    )
    runner = AgentRunner(
        model=ScriptedModel(),
        registry=registry,
        executor=executor,
        context_builder=ContextBuilder(
            budget=TokenBudget(
                max_context_tokens=4_000,
                reserved_output_tokens=500,
            ),
            token_counter=ApproxTokenCounter(),
            policy=ContextPolicy(
                recent_message_limit=4
            ),
        ),
        observability=observability,
        system_instruction="test",
        max_steps=4,
    )
    durable = DurableAgentService(
        runner=runner,
        database=database,
        durable_store=durable_store,
        approval_store=approval_store,
        security=security,
        observability=observability,
        metrics=metrics,
    )
    config = DurableConfig(
        worker_count=2,
        lease_seconds=30.0,
        idle_backoff_seconds=0.01,
        max_transitions_per_claim=8,
    )
    pool = DurableWorkerPool(
        worker_factory=lambda index: DurableWorker(
            runner=runner,
            durable_store=durable_store,
            lifecycle=durable,
            observability=observability,
            config=config,
            worker_id=(
                f"worker_{index}"
            ),
        ),
        config=config,
    )

    return (
        durable,
        pool,
        calls,
    )

@pytest.mark.asyncio
async def test_waiting_approval_survives_and_resumes(
    tmp_path,
) -> None:
    durable, pool, calls = (
        build_runtime(
            tmp_path
        )
    )

    submission = (
        await durable.submit(
            user_id="u1",
            tenant_id="t1",
            user_input="write",
            permissions=frozenset({
                "value.write"
            }),
        )
    )

    await pool.run_until_idle(
        idle_cycles=1
    )

    waiting = durable.get_result(
        submission.run_id
    )
    assert (
        waiting.status
        == DurableRunStatus.WAITING
    )
    assert (
        waiting.waiting_tool_name
        == "write_value"
    )
    assert calls == []

    durable.approve(
        run_id=submission.run_id,
        approved_by="u1",
    )

    await pool.run_until_idle(
        idle_cycles=1
    )

    completed = durable.get_result(
        submission.run_id
    )
    assert (
        completed.status
        == DurableRunStatus.COMPLETED
    )
    assert completed.output == "done"
    assert calls == ["hello"]

    # Terminal Run 不再被 Worker claim，副作用不会因为再次轮询而重复。
    await pool.run_until_idle(
        idle_cycles=1
    )
    assert calls == ["hello"]
