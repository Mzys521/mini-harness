
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

class SecurityAction(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    REDACT = "redact"
    APPROVAL_REQUIRED = "approval_required"

class SecuritySeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass(frozen=True)
class SecurityFinding:
    code: str
    severity: SecuritySeverity
    message: str

@dataclass(frozen=True)
class SecurityDecision:
    action: SecurityAction
    code: str
    reason: str
    findings: tuple[SecurityFinding, ...] = ()
    transformed_text: str | None = None

    @property
    def allowed(self) -> bool:
        return self.action in {
            SecurityAction.ALLOW,
            SecurityAction.REDACT,
        }

@dataclass(frozen=True)
class SecurityAuditEvent:
    """默认不保存 Prompt、Tool Arguments 或模型输出正文。"""
    event_type: str
    action: str
    code: str
    reason: str
    run_id: str | None = None
    tool_name: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )