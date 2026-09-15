import pytest

from harness.persistence.database import Database
from harness.persistence.unit_of_work import UnitOfWork
from harness.state.ids import new_id
from harness.state.models import Checkpoint, Conversation, Run, RunState
from harness.state.transitions import transition_run

@pytest.fixture
def database(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    return db

def test_run_round_trip(database, ):
    conversation = Conversation(
        id = new_id("conv"),
        user_id="user-1",
        tenant_id="tenant-1",
    )

    run = Run(
        id = new_id("run"),
        conversation_id=conversation.id,
    )
    with UnitOfWork(database) as uow:
        uow.conversations.add(conversation)
        uow.runs.add(run)
        uow.commit()
    
    with UnitOfWork(database) as uow:
        loaded = uow.runs.get(run.id)

        assert loaded is not None
        assert loaded.id == run.id
        assert loaded.status == run.status

def test_transaction_rolls_back(database):
    conversation = Conversation(
        id = new_id("conv"),
        user_id="user-1",
        tenant_id="tenant-1",
    )

    try:
        with UnitOfWork(database) as uow:
            uow.conversations.add(conversation)
            raise RuntimeError("boom")

    except RuntimeError:
        pass

    with UnitOfWork(database) as uow:
        loaded = uow.conversations.get(conversation.id)
        assert loaded is None

def test_completed_run_cannot_restart():
    run = Run(
        id = new_id("run"),
        conversation_id=new_id("conv"),
        status=RunState.COMPLETED,
    )

    with pytest.raises(ValueError):
        transition_run(run, RunState.RUNNING,)

def test_latest_checkpoint_wins(database):

    conversation = Conversation(
        id = new_id("conv"),
        user_id="user-1",
        tenant_id="tenant-1",
    )

    run = Run(
        id = new_id("run"),
        conversation_id=conversation.id,
        status=RunState.COMPLETED,
    )

    cp1 = Checkpoint(
        id=new_id("cp"),
        run_id=run.id,
        step_sequence=1,
        state={
            "goal": "build harness",
            "completed_steps": [],
        },
    )

    cp2 = Checkpoint(
        id=new_id("cp"),
        run_id=run.id,
        step_sequence=2,
        state={
            "goal": "build harness",
            "completed_steps": [
                "step 1"
            ],
        },
    )

    with UnitOfWork(database) as uow:
        uow.conversations.add(conversation)
        uow.runs.add(run)
        uow.checkpoints.add(cp1)
        uow.checkpoints.add(cp2)
        uow.commit()

    with UnitOfWork(database) as uow:
        loaded = uow.checkpoints.get_latest(run.id)
        assert loaded is not None
        assert loaded.id == cp2.id
        assert loaded.state == cp2.state


