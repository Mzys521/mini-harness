from dataclasses import asdict

from harness.state.models import (
    Checkpoint,
    Run,
    Step,
    StepState,
    utc_now,
)
from harness.context.models import WorkingState
from harness.state.ids import new_id


def persist_completed_step(*, uow, run: Run, step: Step, working_state,) -> Checkpoint:
    """把已完成的步骤连同工作状态持久化为检查点(同一事务)。
    参数 uow: 工作单元(提供 steps/runs/checkpoints 仓储)
    参数 run: 所属运行实例(原地更新当前步骤)
    参数 step: 已完成的步骤(原地标记为完成)
    参数 working_state: 当前工作状态(将被快照保存为 dict)
    返回: 新建的 Checkpoint
    """

    # 标记步骤为已完成并刷新时间戳
    step.status = StepState.COMPLETED
    step.updated_at = utc_now()

    run.current_step = step.sequence
    run.updated_at = utc_now()

    checkpoint = Checkpoint(
        id=new_id("cp"),
        run_id=run.id,
        step_sequence=step.sequence,
        state=asdict(    # 工作状态转成 dict 快照
            working_state
        ),
    )

    # 三张表在同一事务中写入
    uow.steps.add(step)
    uow.runs.update(run)
    uow.checkpoints.add(checkpoint)

    return checkpoint

def restore_working_state(data: dict ,) -> WorkingState:
    """从 dict 恢复 WorkingState
    参数 data: dict
    返回: WorkingState
    """
    return WorkingState(
        goal = data["goal"],
        facts=data.get("facts", []),
        completed_steps=data.get("completed_steps", [] ,),
        pending_steps=data.get("pending_steps", [],),
    )
