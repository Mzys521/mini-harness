

from harness.state.models import Run, RunState


# 允许的运行状态转换关系
ALLOWED_RUN_TRANSITIONS = {
    RunState.PENDING : {
        RunState.RUNNING,
        RunState.CANCELLED,
    },
    RunState.RUNNING : {
        RunState.WAITING,
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.WAITING : {
        RunState.RUNNING,
        RunState.CANCELLED,
        RunState.FAILED,
    },

    RunState.COMPLETED : set(),
    RunState.FAILED : set(),
    RunState.CANCELLED : set(),
}


def transition_run(run : Run , new_status: RunState) -> None:
    """校验并执行运行状态转换，非法转换抛 ValueError。
    参数 run: 待转换的运行实例(原地更新 status)
    参数 new_status: 目标状态
    """
    allowed = ALLOWED_RUN_TRANSITIONS[run.status]    # 查表: 当前状态允许迁移到的目标集合

    if new_status not in allowed:
        raise ValueError(
            f"invalid run transition: "
            f"{run.status} -> {new_status}"
        )

    run.status = new_status





