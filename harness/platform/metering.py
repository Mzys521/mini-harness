# 文件：harness/platform/metering.py
import asyncio
import logging

from harness.platform.models import UsageMetric

logger = logging.getLogger(__name__)


class UsageReconciler:
    """把 Durable Runtime 的真实执行事实同步成商业 Usage Event。

    采用“幂等事件 + metered marker”模式：如果进程在写入部分 usage 后崩溃，
    下一次同步会重复尝试，但 event_key UNIQUE 保证不会重复计费。
    """

    def __init__(
        self,
        *,
        platform_store,
        durable_store,
        batch_size: int = 100,
        poll_seconds: float = 1.0,
        metrics=None,
    ) -> None:
        self.platform_store = platform_store
        self.durable_store = durable_store
        self.batch_size = batch_size
        self.poll_seconds = poll_seconds
        self.metrics = metrics

    def _sync_record(
        self,
        *,
        run_id: str,
        tenant_id: str,
        plan_id: str,
    ) -> bool:
        record = self.durable_store.get(run_id)
        if record is None:
            return False

        evidence = record.execution.evidence
        usage = evidence.model_usage
        events = (
            (UsageMetric.INPUT_TOKENS, usage.input_tokens),
            (UsageMetric.OUTPUT_TOKENS, usage.output_tokens),
            (UsageMetric.TOOL_CALLS, len(evidence.tool_executions)),
        )
        for metric, quantity in events:
            inserted = self.platform_store.record_usage(
                event_key=f"{run_id}:{metric.value}",
                tenant_id=tenant_id,
                plan_id=plan_id,
                metric=metric,
                quantity=int(quantity),
                run_id=run_id,
                metadata={},
            )
            if inserted and self.metrics is not None:
                self.metrics.platform_usage_events.add(
                    1,
                    {"metric": metric.value},
                )

        self.platform_store.mark_run_metered(
            run_id=run_id,
            tenant_id=tenant_id,
        )
        return True

    def sync_once(self) -> int:
        rows = self.platform_store.list_unmetered_terminal_runs(
            limit=self.batch_size
        )
        return sum(
            1
            for run_id, tenant_id, plan_id in rows
            if self._sync_record(
                run_id=run_id,
                tenant_id=tenant_id,
                plan_id=plan_id,
            )
        )

    def sync_run(self, run_id: str) -> bool:
        row = self.platform_store.get_unmetered_terminal_run(run_id)
        if row is None:
            return False
        _, tenant_id, plan_id = row
        return self._sync_record(
            run_id=run_id,
            tenant_id=tenant_id,
            plan_id=plan_id,
        )

    async def run_forever(self, *, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                self.sync_once()
            except Exception:
                logger.exception("platform usage reconciliation failed")
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.poll_seconds,
                )
            except TimeoutError:
                pass
