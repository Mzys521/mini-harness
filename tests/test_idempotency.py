# 文件：tests/test_idempotency.py
import pytest
from pydantic import BaseModel, ConfigDict

from harness.durable.store import (
    SQLiteIdempotencyStore,
)
from harness.models import ToolCall
from harness.persistence.database import Database
from harness.state.ids import new_id
from harness.state.models import (
    Conversation,
    Run,
)
from harness.tools.definition import (
    ToolContext,
)
from harness.tools.executor import ToolExecutor
from harness.tools.factory import (
    tool_from_pydantic,
)
from harness.tools.registry import (
    ToolRegistry,
)
from harness.tools.result import ToolStatus
from tests.fakes_security import (
    FakeObservability,
    FakeSecurityMetrics,
)

class Args(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )
    value: str

@pytest.mark.asyncio
async def test_started_non_idempotent_side_effect_requires_reconciliation(
    tmp_path,
) -> None:
    database = Database(
        str(
            tmp_path
            / "idempotency.db"
        )
    )
    database.initialize()

    conversation = Conversation(
        id=new_id("conv"),
        user_id="u",
        tenant_id="t",
    )
    run = Run(
        id=new_id("run"),
        conversation_id=(
            conversation.id
        ),
    )
    with database.uow() as uow:
        uow.conversations.add(
            conversation
        )
        uow.runs.add(
            run
        )
        uow.commit()

    store = SQLiteIdempotencyStore(
        database
    )
    calls = []

    def side_effect(
        value: str,
    ):
        calls.append(
            value
        )
        return value

    tool = tool_from_pydantic(
        name="side_effect",
        description="test",
        args_model=Args,
        handler=side_effect,
        side_effect=True,
        idempotent=False,
    )
    registry = ToolRegistry()
    registry.register(
        tool
    )

    call = ToolCall(
        call_id="call_1",
        name="side_effect",
        arguments={
            "value": "x"
        },
    )
    context = ToolContext(
        run_id=run.id
    )

    # 模拟上一个 Worker 已写 STARTED 后崩溃。
    import hashlib
    import json

    payload_hash = hashlib.sha256(
        json.dumps(
            call.arguments,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    store.begin(
        idempotency_key=(
            f"{run.id}:"
            f"{call.call_id}:"
            f"{tool.name}"
        ),
        run_id=run.id,
        call_id=call.call_id,
        tool_name=tool.name,
        payload_hash=payload_hash,
    )

    executor = ToolExecutor(
        registry,
        observability=(
            FakeObservability()
        ),
        metrics=(
            FakeSecurityMetrics()
        ),
        idempotency_store=store,
    )

    result = await executor.execute(
        call,
        context,
    )

    assert (
        result.status
        == ToolStatus.RECONCILIATION_REQUIRED
    )
    assert calls == []
