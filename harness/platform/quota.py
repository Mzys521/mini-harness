# 文件：harness/platform/quota.py
from datetime import UTC, datetime, timedelta

from harness.platform.models import QuotaDecision, UsageMetric


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
    """Business quota：限制租户可以消耗多少 Harness 资源。"""

    def __init__(self, store) -> None:
        self.store = store

    def check_run_submission(self, *, tenant, plan) -> QuotaDecision:
        limits = plan.limits
        active = self.store.count_active_runs(tenant.id)
        if active >= limits.max_concurrent_runs:
            return QuotaDecision(
                allowed=False,
                code="QUOTA_CONCURRENT_RUNS_EXCEEDED",
                reason="当前活跃 Run 数已达到套餐上限。",
                details={
                    "current": active,
                    "limit": limits.max_concurrent_runs,
                },
            )

        day_start, day_end = utc_day_window()
        daily_runs = self.store.sum_usage(
            tenant_id=tenant.id,
            metric=UsageMetric.RUN_SUBMITTED,
            start=day_start,
            end=day_end,
        )
        if daily_runs >= limits.max_runs_per_day:
            return QuotaDecision(
                allowed=False,
                code="QUOTA_DAILY_RUNS_EXCEEDED",
                reason="今日 Run 提交次数已达到套餐上限。",
                details={
                    "current": daily_runs,
                    "limit": limits.max_runs_per_day,
                },
            )

        month_start, month_end = utc_month_window()
        checks = (
            (
                UsageMetric.INPUT_TOKENS,
                limits.max_input_tokens_per_month,
                "QUOTA_INPUT_TOKENS_EXCEEDED",
            ),
            (
                UsageMetric.OUTPUT_TOKENS,
                limits.max_output_tokens_per_month,
                "QUOTA_OUTPUT_TOKENS_EXCEEDED",
            ),
            (
                UsageMetric.TOOL_CALLS,
                limits.max_tool_calls_per_month,
                "QUOTA_TOOL_CALLS_EXCEEDED",
            ),
        )
        for metric, limit, code in checks:
            current = self.store.sum_usage(
                tenant_id=tenant.id,
                metric=metric,
                start=month_start,
                end=month_end,
            )
            if current >= limit:
                return QuotaDecision(
                    allowed=False,
                    code=code,
                    reason=f"本月 {metric.value} 已达到套餐上限。",
                    details={"current": current, "limit": limit},
                )

        return QuotaDecision(
            allowed=True,
            code="QUOTA_ALLOWED",
            reason="当前租户配额允许提交新的 Run。",
            details={"active_runs": active},
        )
