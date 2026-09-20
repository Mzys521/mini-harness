# 文件：harness/platform/protocol.py
from typing import Protocol

from harness.platform.models import UsageEvent


class BillingExporter(Protocol):
    """把内部 Usage Ledger 导出到 Stripe / 自建账单系统等外部计费后端。"""

    async def export(self, events: list[UsageEvent]) -> None:
        ...
