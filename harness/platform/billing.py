# 文件：harness/platform/billing.py
from decimal import Decimal, ROUND_HALF_UP

from harness.platform.models import BillingLine, BillingPreview, UsageMetric


class BillingService:
    """内部 Usage Ledger → Billing Preview。

    这里只负责可审计的用量与价格计算，不直接调用支付厂商。
    Stripe / 其他 Provider 应通过后续 Billing Exporter Adapter 接入。
    """

    def __init__(self, *, store, currency: str = "USD") -> None:
        self.store = store
        self.currency = currency

    def preview(self, *, tenant_id: str, start, end) -> BillingPreview:
        usage = self.store.usage_by_plan(
            tenant_id=tenant_id,
            start=start,
            end=end,
        )
        lines: list[BillingLine] = []
        total = 0

        for (plan_id, metric_name), quantity in sorted(usage.items()):
            plan = self.store.get_plan(plan_id)
            if plan is None:
                continue
            rate = next(
                (
                    item
                    for item in plan.rates
                    if item.metric.value == metric_name
                ),
                None,
            )
            if rate is None:
                continue

            billable_units = max(0, int(quantity) - rate.included_units)
            amount = self._amount_microusd(
                quantity=billable_units,
                unit_size=rate.unit_size,
                price_microusd=rate.price_microusd,
            )
            line = BillingLine(
                metric=metric_name,
                quantity=int(quantity),
                included_units=rate.included_units,
                billable_units=billable_units,
                unit_size=rate.unit_size,
                price_microusd=rate.price_microusd,
                amount_microusd=amount,
            )
            lines.append(line)
            total += amount

        return BillingPreview(
            tenant_id=tenant_id,
            period_start=start,
            period_end=end,
            currency=self.currency,
            lines=tuple(lines),
            total_microusd=total,
        )

    @staticmethod
    def _amount_microusd(
        *,
        quantity: int,
        unit_size: int,
        price_microusd: int,
    ) -> int:
        if unit_size <= 0:
            raise ValueError("billing unit_size must be positive")
        raw = (
            Decimal(quantity)
            * Decimal(price_microusd)
            / Decimal(unit_size)
        )
        return int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
