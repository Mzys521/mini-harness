# 文件：harness/context/models.py
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"

@dataclass(frozen=True)
class Message:
    role: MessageRole
    content: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass
class WorkingState:
    goal: str
    facts: dict[str, Any] = field(
        default_factory=dict
    )
    completed_steps: list[str] = field(
        default_factory=list
    )
    pending_steps: list[str] = field(
        default_factory=list
    )

@dataclass(frozen=True)
class ModelContext:
    instructions: str
    input_data: list[dict[str, str]]
    estimated_tokens: int
    dropped_messages: int
    dropped_sections: tuple[str, ...] = ()
