# 文件：harness/durable/models.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from harness.models import RunEvidence, ToolCall
from harness.tools.definition import ToolContext

class ExecutionPhase(StrEnum):
    MODEL = "model"
    TOOL = "tool"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_RECONCILIATION = "waiting_reconciliation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class DurableRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AgentExecutionState:
    """可以写入数据库并在另一个 Worker 恢复的 Agent 状态。"""

    run_id: str
    user_input: str
    instructions: str
    current_input: list[dict[str, Any]]
    tool_context: ToolContext

    phase: ExecutionPhase = ExecutionPhase.MODEL
    model_step: int = 0
    transition_count: int = 0
    previous_response_id: str | None = None

    pending_tool_calls: list[ToolCall] = field(
        default_factory=list
    )
    pending_tool_index: int = 0
    tool_outputs: list[dict[str, Any]] = field(
        default_factory=list
    )

    evidence: RunEvidence = field(
        default_factory=RunEvidence
    )
    final_output: str | None = None
    error_message: str | None = None
    transition_data: dict[str, Any] = field(default_factory=dict)
    applied_instructions: list[str] = field(default_factory=list)

    @property
    def current_tool_call(
        self,
    ) -> ToolCall | None:
        if (
            self.phase
            not in {
                ExecutionPhase.TOOL,
                ExecutionPhase.WAITING_APPROVAL,
                ExecutionPhase.WAITING_RECONCILIATION,
            }
        ):
            return None

        if (
            self.pending_tool_index
            >= len(
                self.pending_tool_calls
            )
        ):
            return None

        return self.pending_tool_calls[
            self.pending_tool_index
        ]

@dataclass(frozen=True)
class DurableRunRecord:
    run_id: str
    status: DurableRunStatus
    version: int
    execution: AgentExecutionState
    lease_owner: str | None
    lease_expires_at: datetime | None
    available_at: datetime
    cancel_requested: bool
    trace_carrier: dict[str, str]
    created_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class DurableSubmission:
    conversation_id: str
    run_id: str
    status: DurableRunStatus
    blocked: bool = False
    output: str | None = None

@dataclass(frozen=True)
class DurableResult:
    conversation_id: str
    run_id: str
    status: DurableRunStatus
    output: str | None
    waiting_call_id: str | None = None
    waiting_tool_name: str | None = None
    error_message: str | None = None

class DurableConflictError(RuntimeError):
    """Version / Lease 已被其他 Worker 改变。"""

class DurableLeaseLostError(RuntimeError):
    """当前 Worker 已不再拥有这个 Run。"""
