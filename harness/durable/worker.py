# 文件：harness/durable/worker.py
import asyncio
import logging
import uuid
from time import perf_counter

from harness.durable.models import (
    DurableLeaseLostError,
    DurableRunStatus,
    ExecutionPhase,
)
from harness.durable.tracing import (
    inject_current_context,
    use_trace_carrier,
)

logger = logging.getLogger(
    __name__
)

class DurableWorker:
    """一个 Worker 每次 claim 一个 Durable Run，并在每个 Transition 后落库。"""

    def __init__(
        self,
        *,
        runner,
        durable_store,
        lifecycle,
        observability,
        config,
        worker_id: str | None = None,
    ) -> None:
        self.runner = runner
        self.durable_store = durable_store
        self.lifecycle = lifecycle
        self.observability = observability
        self.config = config
        self.worker_id = (
            worker_id
            or f"worker_{uuid.uuid4().hex[:10]}"
        )

    async def run_once(self) -> bool:
        record = (
            self.durable_store.claim_next(
                worker_id=self.worker_id,
                lease_seconds=(
                    self.config.lease_seconds
                ),
            )
        )

        if record is None:
            return False

        state = record.execution
        version = record.version

        try:
            with use_trace_carrier(
                record.trace_carrier
            ):
                with self.observability.span(
                    "durable.worker.segment",
                    {
                        "agent.run_id": (
                            record.run_id
                        ),
                        "worker.id": (
                            self.worker_id
                        ),
                    },
                ):
                    for _ in range(
                        self.config.max_transitions_per_claim
                    ):
                        if (
                            self.durable_store.is_cancel_requested(
                                record.run_id
                            )
                        ):
                            state.phase = (
                                ExecutionPhase.CANCELLED
                            )
                            state.transition_count += 1

                            carrier = (
                                inject_current_context()
                            )
                            version = (
                                self.durable_store.save_claimed(
                                    run_id=record.run_id,
                                    worker_id=self.worker_id,
                                    expected_version=version,
                                    execution=state,
                                    status=(
                                        DurableRunStatus.CANCELLED
                                    ),
                                    trace_carrier=carrier,
                                    release_lease=True,
                                    lease_seconds=(
                                        self.config.lease_seconds
                                    ),
                                )
                            )
                            self.lifecycle.persist_cancelled(
                                state
                            )
                            return True

                        previous_phase = (
                            state.phase
                        )
                        desktop = getattr(self.lifecycle, "desktop", None)
                        if desktop is not None:
                            desktop.apply_instructions(state)
                            if desktop.is_paused(record.run_id):
                                self.durable_store.save_claimed(
                                    run_id=record.run_id, worker_id=self.worker_id,
                                    expected_version=version, execution=state,
                                    status=DurableRunStatus.WAITING,
                                    trace_carrier=inject_current_context(), release_lease=True,
                                    lease_seconds=self.config.lease_seconds,
                                )
                                # Resume can arrive between the pause check and lease release.
                                if not desktop.is_paused(record.run_id):
                                    desktop.execute("UPDATE durable_runs SET status='pending' WHERE run_id=? AND status='waiting' AND lease_owner IS NULL", (record.run_id,))
                                return True

                        # WAITING 状态不应该继续消耗 Worker。
                        if state.phase in {
                            ExecutionPhase.WAITING_APPROVAL,
                            ExecutionPhase.WAITING_RECONCILIATION,
                        }:
                            carrier = (
                                inject_current_context()
                            )
                            self.durable_store.save_claimed(
                                run_id=record.run_id,
                                worker_id=self.worker_id,
                                expected_version=version,
                                execution=state,
                                status=(
                                    DurableRunStatus.WAITING
                                ),
                                trace_carrier=carrier,
                                release_lease=True,
                                lease_seconds=(
                                    self.config.lease_seconds
                                ),
                            )
                            self.lifecycle.persist_waiting(
                                state
                            )
                            return True

                        # 在调用 Model / Tool 前续租，避免长 I/O 期间被过早抢占。
                        self.durable_store.heartbeat(
                            run_id=record.run_id,
                            worker_id=self.worker_id,
                            lease_seconds=(
                                self.config.lease_seconds
                            ),
                        )

                        started = perf_counter()
                        state = await self.runner.advance(
                            state,
                            pause_on_approval=True,
                        )
                        state.transition_data["duration"] = round((perf_counter() - started) * 1000)

                        if (
                            state.phase
                            == ExecutionPhase.COMPLETED
                        ):
                            self.lifecycle.prepare_completed(
                                state
                            )

                        if (
                            state.phase
                            == ExecutionPhase.COMPLETED
                        ):
                            durable_status = (
                                DurableRunStatus.COMPLETED
                            )
                            release = True

                        elif state.phase in {
                            ExecutionPhase.WAITING_APPROVAL,
                            ExecutionPhase.WAITING_RECONCILIATION,
                        }:
                            durable_status = (
                                DurableRunStatus.WAITING
                            )
                            release = True

                        elif (
                            state.phase
                            == ExecutionPhase.CANCELLED
                        ):
                            durable_status = (
                                DurableRunStatus.CANCELLED
                            )
                            release = True

                        else:
                            durable_status = (
                                DurableRunStatus.RUNNING
                            )
                            release = False

                        carrier = (
                            inject_current_context()
                        )

                        version = (
                            self.durable_store.save_claimed(
                                run_id=record.run_id,
                                worker_id=self.worker_id,
                                expected_version=version,
                                execution=state,
                                status=durable_status,
                                trace_carrier=carrier,
                                release_lease=release,
                                lease_seconds=(
                                    self.config.lease_seconds
                                ),
                            )
                        )

                        # Durable State 已成功 Commit 后，再同步 Phase 4 Step / Checkpoint。
                        self.lifecycle.persist_transition(
                            state=state,
                            previous_phase=(
                                previous_phase
                            ),
                        )

                        if (
                            state.phase
                            == ExecutionPhase.COMPLETED
                        ):
                            self.lifecycle.persist_completed(
                                state
                            )
                            return True

                        if state.phase in {
                            ExecutionPhase.WAITING_APPROVAL,
                            ExecutionPhase.WAITING_RECONCILIATION,
                        }:
                            self.lifecycle.persist_waiting(
                                state
                            )
                            return True

                        if (
                            state.phase
                            == ExecutionPhase.CANCELLED
                        ):
                            self.lifecycle.persist_cancelled(
                                state
                            )
                            return True

                    # 为了公平性，一个 claim 最多跑有限 Transition，然后重新入队。
                    carrier = (
                        inject_current_context()
                    )
                    self.durable_store.release_for_retry(
                        run_id=record.run_id,
                        worker_id=self.worker_id,
                        expected_version=version,
                        execution=state,
                        delay_seconds=0.0,
                        trace_carrier=carrier,
                    )
                    return True

        except DurableLeaseLostError:
            # Stale Worker 不能继续写业务状态。
            logger.warning(
                "durable lease lost",
                extra={
                    "run_id": record.run_id,
                    "worker_id": self.worker_id,
                },
            )
            return True

        except Exception as exc:
            state.phase = (
                ExecutionPhase.FAILED
            )
            state.error_message = str(
                exc
            )

            try:
                carrier = (
                    inject_current_context()
                )
                self.durable_store.save_claimed(
                    run_id=record.run_id,
                    worker_id=self.worker_id,
                    expected_version=version,
                    execution=state,
                    status=DurableRunStatus.FAILED,
                    trace_carrier=carrier,
                    release_lease=True,
                    lease_seconds=(
                        self.config.lease_seconds
                    ),
                )
                self.lifecycle.persist_failed(
                    state,
                    exc,
                )
            except Exception:
                logger.exception(
                    "failed to persist durable failure",
                    extra={
                        "run_id": record.run_id,
                        "worker_id": self.worker_id,
                    },
                )

            return True

class DurableWorkerPool:
    """Python 3.11+ TaskGroup 管理进程内多个 Worker Loop。"""

    def __init__(
        self,
        *,
        worker_factory,
        config,
    ) -> None:
        self.worker_factory = (
            worker_factory
        )
        self.config = config

    async def run_until_idle(
        self,
        *,
        idle_cycles: int = 3,
    ) -> None:
        async def worker_loop(
            worker,
        ) -> None:
            idle = 0

            while idle < idle_cycles:
                worked = (
                    await worker.run_once()
                )

                if worked:
                    idle = 0
                    continue

                idle += 1
                await asyncio.sleep(
                    self.config.idle_backoff_seconds
                )

        # Structured Concurrency：所有 Worker 都属于同一个明确生命周期。
        async with asyncio.TaskGroup() as group:
            for index in range(
                self.config.worker_count
            ):
                group.create_task(
                    worker_loop(
                        self.worker_factory(
                            index
                        )
                    ),
                    name=(
                        f"durable-worker-{index}"
                    ),
                )

    async def run_forever(
        self,
        *,
        stop_event: asyncio.Event,
    ) -> None:
        async def worker_loop(
            worker,
        ) -> None:
            while not stop_event.is_set():
                worked = (
                    await worker.run_once()
                )
                if not worked:
                    await asyncio.sleep(
                        self.config.poll_interval_seconds
                    )

        async with asyncio.TaskGroup() as group:
            for index in range(
                self.config.worker_count
            ):
                group.create_task(
                    worker_loop(
                        self.worker_factory(
                            index
                        )
                    ),
                    name=(
                        f"durable-worker-{index}"
                    ),
                )
