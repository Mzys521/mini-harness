# 文件：harness/application.py
import logging
from dataclasses import (
    asdict,
    dataclass,
    field,
)
from time import perf_counter

from harness.context.models import (
    WorkingState,
)
from harness.models import (
    RunEvidence,
    SecurityDecisionRecord,
)
from harness.security.models import (
    SecurityAction,
)
from harness.state.ids import new_id
from harness.state.models import (
    Checkpoint,
    Conversation,
    Run,
    RunStatus,
    utc_now,
)
from harness.tools.definition import (
    ToolContext,
)

logger = logging.getLogger(
    __name__
)

@dataclass(frozen=True)
class ApplicationResult:
    conversation_id: str
    run_id: str
    output: str
    steps: int
    evidence: RunEvidence = field(
        default_factory=RunEvidence
    )
    blocked: bool = False

class PersistentAgentService:
    def __init__(
        self,
        *,
        runner,
        database,
        observability,
        metrics,
        security=None,
    ) -> None:
        self.runner = runner
        self.database = database
        self.observability = observability
        self.metrics = metrics

        # Optional 保证 Phase 8 之前的测试/自定义嵌入仍能渐进迁移。
        self.security = security

    async def ask(
        self,
        *,
        user_id: str,
        tenant_id: str,
        user_input: str,
        permissions: frozenset[str],
        conversation_id: str | None = None,
    ) -> ApplicationResult:
        started = perf_counter()

        if conversation_id is None:
            conversation = Conversation(
                id=new_id("conv"),
                user_id=user_id,
                tenant_id=tenant_id,
            )
            history = []

            with self.database.uow() as uow:
                uow.conversations.add(
                    conversation
                )
                uow.commit()
        else:
            with self.database.uow() as uow:
                conversation = (
                    uow.conversations.get(
                        conversation_id
                    )
                )

                if conversation is None:
                    raise ValueError(
                        "conversation not found"
                    )

                # Tenant Boundary 必须由应用确定性验证。
                if (
                    conversation.tenant_id
                    != tenant_id
                ):
                    raise PermissionError(
                        "conversation tenant mismatch"
                    )

                history = (
                    uow.messages.list_recent(
                        conversation_id=conversation.id,
                        limit=100,
                    )
                )

        run = Run(
            id=new_id("run"),
            conversation_id=conversation.id,
        )
        evidence = RunEvidence()

        self.metrics.agent_runs.add(
            1,
            {"operation": "ask"},
        )

        try:
            with self.observability.span(
                "agent.run",
                {"agent.run_id": run.id},
            ) as span:
                # 1. Input Guardrail：在 Model 和原始 Message 持久化之前检查。
                safe_input = user_input

                if self.security is not None:
                    (
                        safe_input,
                        input_decisions,
                    ) = self.security.inspect_input(
                        text=user_input,
                        run_id=run.id,
                    )

                    for decision in input_decisions:
                        evidence.security_decisions.append(
                            SecurityDecisionRecord(
                                stage="input",
                                action=decision.action.value,
                                code=decision.code,
                            )
                        )

                    blocking = next(
                        (
                            item
                            for item in input_decisions
                            if item.action
                            == SecurityAction.BLOCK
                        ),
                        None,
                    )

                    if blocking is not None:
                        # 不把被阻止的原始敏感输入写进 Message Store。
                        run.status = (
                            RunStatus.BLOCKED
                        )
                        run.error_message = (
                            blocking.code
                        )
                        run.updated_at = (
                            utc_now()
                        )
                        blocked_output = (
                            "请求被安全策略阻止。"
                        )

                        with self.database.uow() as uow:
                            uow.runs.add(
                                run
                            )
                            uow.messages.add_user(
                                conversation_id=conversation.id,
                                content=(
                                    "[BLOCKED_INPUT_OMITTED]"
                                ),
                            )
                            uow.messages.add_assistant(
                                conversation_id=conversation.id,
                                content=blocked_output,
                            )
                            uow.commit()

                        span.set_attribute(
                            "agent.status",
                            "blocked",
                        )
                        span.set_attribute(
                            "security.code",
                            blocking.code,
                        )
                        self.metrics.agent_duration.record(
                            perf_counter() - started,
                            {"status": "blocked"},
                        )

                        return ApplicationResult(
                            conversation_id=conversation.id,
                            run_id=run.id,
                            output=blocked_output,
                            steps=0,
                            evidence=evidence,
                            blocked=True,
                        )

                working_state = WorkingState(
                    goal=safe_input
                )

                # 2. Input Guardrail 通过后才保存允许进入业务链路的输入。
                with self.database.uow() as uow:
                    uow.runs.add(
                        run
                    )
                    uow.messages.add_user(
                        conversation_id=conversation.id,
                        content=safe_input,
                    )
                    uow.commit()

                run.status = (
                    RunStatus.RUNNING
                )
                run.updated_at = (
                    utc_now()
                )

                with self.database.uow() as uow:
                    uow.runs.update(
                        run
                    )
                    uow.commit()

                result = await self.runner.run(
                    safe_input,
                    history=history,
                    tool_context=ToolContext(
                        run_id=run.id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        permissions=permissions,
                    ),
                    working_state=working_state,
                )

                # Runner 产生 Tool / Model Evidence；合并 Input Security Evidence。
                result.evidence.security_decisions[
                    0:0
                ] = evidence.security_decisions

                # 3. Output Guardrail 必须发生在持久化最终 Assistant Message 之前。
                safe_output = (
                    result.output
                )

                if self.security is not None:
                    (
                        safe_output,
                        output_decisions,
                    ) = self.security.inspect_output(
                        text=result.output,
                        run_id=run.id,
                    )

                    for decision in output_decisions:
                        result.evidence.security_decisions.append(
                            SecurityDecisionRecord(
                                stage="output",
                                action=decision.action.value,
                                code=decision.code,
                            )
                        )

                    blocking_output = next(
                        (
                            item
                            for item in output_decisions
                            if item.action
                            == SecurityAction.BLOCK
                        ),
                        None,
                    )

                    if blocking_output is not None:
                        safe_output = (
                            "响应被安全策略阻止。"
                        )

                result.output = (
                    safe_output
                )

                run.status = (
                    RunStatus.COMPLETED
                )
                run.provider_response_id = (
                    result.response_id
                )
                run.updated_at = (
                    utc_now()
                )

                checkpoint = Checkpoint(
                    id=new_id("cp"),
                    run_id=run.id,
                    step_sequence=result.steps,
                    state={
                        "working_state": asdict(
                            working_state
                        ),
                        "provider_response_id": (
                            result.response_id
                        ),
                        # 只保存 Guardrail 处理后的最终输出。
                        "final_output": safe_output,
                    },
                    created_at=utc_now(),
                )

                with self.database.uow() as uow:
                    uow.messages.add_assistant(
                        conversation_id=conversation.id,
                        content=safe_output,
                    )
                    uow.runs.update(
                        run
                    )
                    uow.checkpoints.add(
                        checkpoint
                    )
                    uow.commit()

                duration = (
                    perf_counter()
                    - started
                )
                span.set_attribute(
                    "agent.steps",
                    result.steps,
                )
                span.set_attribute(
                    "agent.status",
                    "completed",
                )
                self.metrics.agent_duration.record(
                    duration,
                    {"status": "completed"},
                )

                logger.info(
                    "agent run completed",
                    extra={
                        "run_id": run.id,
                        "conversation_id": conversation.id,
                        "steps": result.steps,
                        "duration_seconds": duration,
                    },
                )

                return ApplicationResult(
                    conversation_id=conversation.id,
                    run_id=run.id,
                    output=safe_output,
                    steps=result.steps,
                    evidence=result.evidence,
                    blocked=False,
                )

        except Exception as exc:
            run.status = (
                RunStatus.FAILED
            )
            run.error_message = (
                str(exc)
            )
            run.updated_at = (
                utc_now()
            )

            try:
                with self.database.uow() as uow:
                    # 如果 run 尚未 add，update 可能没有目标；
                    # Repository 的 update 应安全地处理或由实际实现 upsert。
                    uow.runs.update(
                        run
                    )
                    uow.commit()
            except Exception:
                logger.exception(
                    "failed to persist run failure",
                    extra={"run_id": run.id},
                )

            self.metrics.agent_errors.add(
                1,
                {"status": "failed"},
            )
            self.metrics.agent_duration.record(
                perf_counter() - started,
                {"status": "failed"},
            )
            logger.exception(
                "agent run failed",
                extra={"run_id": run.id},
            )
            raise

        finally:
            if self.security is not None:
                # 释放 Run-scoped 的 In-memory Security State。
                self.security.finish_run(
                    run.id
                )