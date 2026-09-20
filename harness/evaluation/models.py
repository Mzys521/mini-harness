# 文件：harness/evaluation/models.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from harness.models import (
    RunEvidence,
)

@dataclass(frozen=True)
class EvalCase:
    id: str
    input: str
    tags: tuple[str, ...] = ()
    expected_answer_contains: tuple[str, ...] = ()
    expected_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    max_steps: int | None = None
    reference_answer: str | None = None
    rubric: str | None = None

    # Phase 9：安全专项期望。
    expected_security_codes: tuple[str, ...] = ()
    expect_blocked: bool | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(frozen=True)
class EvalSample:
    case_id: str
    output: str
    steps: int
    evidence: RunEvidence
    run_id: str | None = None
    blocked: bool = False

@dataclass(frozen=True)
class EvalScore:
    evaluator: str
    score: float
    passed: bool
    reason: str
    details: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(frozen=True)
class EvalCaseResult:
    case: EvalCase
    sample: EvalSample
    scores: tuple[EvalScore, ...]

    @property
    def passed(
        self,
    ) -> bool:
        return all(
            score.passed
            for score in self.scores
        )

    @property
    def average_score(
        self,
    ) -> float:
        if not self.scores:
            return 1.0

        return (
            sum(
                item.score
                for item in self.scores
            )
            / len(self.scores)
        )

@dataclass(frozen=True)
class EvalSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    average_score: float

@dataclass(frozen=True)
class EvalRunResult:
    suite_name: str
    started_at: datetime
    completed_at: datetime
    results: tuple[EvalCaseResult, ...]
    summary: EvalSummary

def utc_now() -> datetime:
    return datetime.now(UTC)