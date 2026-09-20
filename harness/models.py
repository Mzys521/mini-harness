# 文件：harness/models.py
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]

@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(
        self,
        other: "ModelUsage",
    ) -> "ModelUsage":
        return ModelUsage(
            input_tokens=(
                self.input_tokens
                + other.input_tokens
            ),
            output_tokens=(
                self.output_tokens
                + other.output_tokens
            ),
            total_tokens=(
                self.total_tokens
                + other.total_tokens
            ),
            cached_input_tokens=(
                self.cached_input_tokens
                + other.cached_input_tokens
            ),
        )

@dataclass(frozen=True)
class ToolExecutionRecord:
    call_id: str
    name: str
    arguments: dict[str, Any]
    status: str
    error_code: str | None = None
    security_code: str | None = None

@dataclass(frozen=True)
class SecurityDecisionRecord:
    """供 Evaluation 消费的最小安全事实，不保存敏感正文。"""
    stage: str
    action: str
    code: str

@dataclass
class RunEvidence:
    tool_executions: list[ToolExecutionRecord] = field(
        default_factory=list
    )
    security_decisions: list[SecurityDecisionRecord] = field(
        default_factory=list
    )
    model_usage: ModelUsage = field(
        default_factory=ModelUsage
    )

@dataclass
class ModelResult:
    text: str = ""
    tool_calls: list[ToolCall] = field(
        default_factory=list
    )
    response_id: str | None = None
    usage: ModelUsage = field(
        default_factory=ModelUsage
    )

@dataclass
class RunResult:
    output: str
    steps: int
    response_id: str | None = None
    evidence: RunEvidence = field(
        default_factory=RunEvidence
    )