# 文件：tests/test_durable_store.py
import asyncio

import pytest

from harness.context.models import WorkingState
from harness.durable.models import (
    AgentExecutionState,
)
from harness.durable.store import (
    SQLiteDurableStore,
)
from harness.persistence.database import (
    Database,
)
from harness.state.ids import new_id
from harness.state.models import (
    Conversation,
    Run,
)
from harness.tools.definition import (
    ToolContext,
)

@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed(
    tmp_path,
) -> None:
    database = Database(
        str(
            tmp_path
            / "lease.db"
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

    store = SQLiteDurableStore(
        database
    )
    store.enqueue(
        run_id=run.id,
        execution=AgentExecutionState(
            run_id=run.id,
            user_input="x",
            instructions="test",
            current_input=[
                {
                    "role": "user",
                    "content": "x",
                }
            ],
            tool_context=ToolContext(
                run_id=run.id
            ),
        ),
    )

    first = store.claim_next(
        worker_id="a",
        lease_seconds=0.02,
    )
    assert first is not None
    assert first.lease_owner == "a"

    await asyncio.sleep(
        0.04
    )

    second = store.claim_next(
        worker_id="b",
        lease_seconds=10,
    )
    assert second is not None
    assert second.run_id == run.id
    assert second.lease_owner == "b"
    assert (
        second.version
        > first.version
    )
