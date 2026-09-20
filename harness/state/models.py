# 文件：harness/state/models.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

def utc_now() -> datetime:
    return datetime.now(UTC)

class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepType(StrEnum):
    MODEL = "model"
    TOOL = "tool"
    CHECKPOINT = "checkpoint"
    SECURITY = "security"
    SYSTEM = "system"

@dataclass
class Conversation:
    id: str
    user_id: str
    tenant_id: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

@dataclass
class Run:
    id: str
    conversation_id: str
    status: RunStatus = RunStatus.PENDING
    current_step: int = 0
    provider_response_id: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

@dataclass
class Step:
    id: str
    run_id: str
    sequence: int
    type: StepType
    status: StepStatus = StepStatus.PENDING
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

@dataclass
class Checkpoint:
    id: str
    run_id: str
    step_sequence: int
    state: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

@dataclass
class RuntimeEvent:
    id: str
    run_id: str
    event_type: str
    payload: dict[str, Any]
    step_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
