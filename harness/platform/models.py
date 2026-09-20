# 文件：harness/platform/models.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"

class ApiKeyStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"

class UsageMetric(StrEnum):
    RUN_SUBMITTED = "run_submitted"
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    TOOL_CALLS = "tool_calls"

@dataclass(frozen=True)
class PlanLimits:
    max_concurrent_runs: int = 2
    max_runs_per_day: int = 100
    max_input_tokens_per_month: int = 1_000_000
    max_output_tokens_per_month: int = 500_000
    max_tool_calls_per_month: int = 10_000

@dataclass(frozen=True)
class MeterRate:
    metric: UsageMetric
    unit_size: int
    price_microusd: int
    included_units: int = 0

@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    limits: PlanLimits
    tool_permissions: frozenset[str] = field(default_factory=frozenset)
    rates: tuple[MeterRate, ...] = ()
    active: bool = True

@dataclass(frozen=True)
class Tenant:
    id: str
    name: str
    plan_id: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class ApiKeyRecord:
    id: str
    tenant_id: str
    name: str
    key_hash: str
    scopes: frozenset[str]
    status: ApiKeyStatus
    created_at: datetime
    last_used_at: datetime | None = None

@dataclass(frozen=True)
class Principal:
    tenant_id: str
    api_key_id: str
    scopes: frozenset[str]

    def has_scope(self, scope: str) -> bool:
        return (
            "platform:admin" in self.scopes
            or scope in self.scopes
        )

@dataclass(frozen=True)
class UsageEvent:
    id: str
    event_key: str
    tenant_id: str
    plan_id: str
    metric: UsageMetric
    quantity: int
    run_id: str | None
    metadata: dict[str, Any]
    created_at: datetime

@dataclass(frozen=True)
class UsageSummary:
    tenant_id: str
    period_start: datetime
    period_end: datetime
    quantities: dict[str, int]

@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    code: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class BillingLine:
    metric: str
    quantity: int
    included_units: int
    billable_units: int
    unit_size: int
    price_microusd: int
    amount_microusd: int

@dataclass(frozen=True)
class BillingPreview:
    tenant_id: str
    period_start: datetime
    period_end: datetime
    currency: str
    lines: tuple[BillingLine, ...]
    total_microusd: int

@dataclass(frozen=True)
class IssuedApiKey:
    record: ApiKeyRecord
    secret: str

def utc_now() -> datetime:
    return datetime.now(UTC)
