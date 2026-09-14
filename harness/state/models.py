from dataclasses import dataclass , field
from datetime import datetime , UTC
from enum import StrEnum
from typing import Any

class RunState(StrEnum):
    """一次运行(Run)的状态"""
    PENDING = "pending"    # 等待执行
    RUNNING = "running"    # 执行中
    WAITING = "waiting"    # 等待中(如等外部输入)
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"    # 已失败
    CANCELLED = "cancelled"    # 已取消

class StepState(StrEnum):
    """单个步骤(Step)的状态"""
    PENDING = "pending"    # 待执行
    RUNNING = "running"    # 执行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"    # 已失败

class StepType(StrEnum):
    """步骤类型"""
    MODEL = "model"    # 模型调用
    TOOL = "tool"    # 工具调用
    CHECKPOINT = "checkpoint"    # 检查点

def utc_now() -> datetime:
    """获取当前 UTC 时间(统一时间来源)"""
    return datetime.now(UTC)

@dataclass
class Conversation:
    """一次用户会话"""
    id: str    # 会话ID
    user_id: str    # 所属用户
    tenant_id: str    # 所属租户
    created_at: datetime = field(default_factory=utc_now)    # 创建时间
    updated_at: datetime = field(default_factory=utc_now)    # 更新时间

@dataclass
class Run:
    """一次 Agent 运行实例"""
    id : str    # 运行ID
    conversation_id: str    # 所属会话ID
    status: RunState = RunState.PENDING    # 运行状态
    current_step: int = 0    # 当前步骤序号
    error_message: str | None = None    # 失败原因
    created_at: datetime = field(default_factory=utc_now)    # 创建时间
    updated_at: datetime = field(default_factory=utc_now)    # 更新时间


@dataclass
class Step:
    """运行中的单个执行步骤"""
    id : str    # 步骤ID
    run_id: str    # 所属运行ID
    sequence: int    # 步骤序号(同一运行内唯一)
    type : StepType    # 步骤类型(模型/工具/检查点)
    status: StepState    # 步骤状态
    input_data: dict[str, Any] = field(default_factory=dict)    # 输入数据
    output_data: dict[str, Any] = field(default_factory=dict)    # 输出数据
    error_message: str | None = None    # 失败原因
    created_at: datetime = field(default_factory=utc_now)    # 创建时间
    updated_at: datetime = field(default_factory=utc_now)    # 更新时间

@dataclass
class Checkpoint:
    """检查点: 某一步完成后的状态快照(用于崩溃恢复)"""
    id : str    # 检查点ID
    run_id: str    # 所属运行ID
    step_sequence: int    # 对应步骤序号
    state: dict[str, Any]    # 工作状态快照
    created_at: datetime = field(default_factory=utc_now)    # 创建时间

@dataclass
class RuntimeEvent:
    id: str
    run_id: str
    event_type: str
    payload: dict[str, Any]
    step_id: str | None = None
    created_at: datetime = field(
        default_factory=utc_now
    )









