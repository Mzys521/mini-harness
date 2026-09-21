# 文件：harness/platform/quota.py
from datetime import UTC, datetime, timedelta

from harness.platform.models import QuotaDecision


def utc_day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def utc_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


class QuotaService:
    """Compatibility facade: personal installations have no usage quotas."""

    def __init__(self, store) -> None:
        self.store = store

    def check_run_submission(self, *, tenant, plan) -> QuotaDecision:
        return QuotaDecision(allowed=True, code="UNLIMITED", reason="个人工作区不限制用量")
