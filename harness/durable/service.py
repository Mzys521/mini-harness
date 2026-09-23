# 文件：harness/durable/service.py
from dataclasses import asdict

from harness.context.models import WorkingState
from harness.durable.models import (
    DurableResult,
    DurableRunStatus,
    DurableSubmission,
    ExecutionPhase,
)
from harness.durable.serialization import (
    execution_to_dict,
)
from harness.durable.tracing import (
    inject_current_context,
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
    RuntimeEvent,
    Step,
    StepStatus,
    StepType,
    utc_now,
)
from harness.tools.definition import ToolContext

class DurableAgentService:
    """Client-facing Durable Run API：submit / status / approve / cancel。"""

    def __init__(
        self,
        *,
        runner,
        database,
        durable_store,
        approval_store,
        security,
        observability,
        metrics,
        events=None,
    ) -> None:
        self.runner = runner
        self.database = database
        self.durable_store = durable_store
        self.approval_store = approval_store
        self.security = security
        self.observability = observability
        self.metrics = metrics
        # 可选事件出口（RunEventBroker.publish）。为 None 时所有 _emit 都是空操作。
        self.events = events

    def _emit(self, run_id: str, event: dict) -> None:
        if self.events is not None:
            self.events(run_id, event)

    async def submit(
        self,
        *,
        user_id: str,
        tenant_id: str,
        user_input: str,
        permissions: frozenset[str],
        conversation_id: str | None = None,
        workspace_id: str | None = None,
        workspace_path: str | None = None,
        knowledge_path: str | None = None,
        external_context: str | None = None,
        tool_names: frozenset[str] | None = None,
    ) -> DurableSubmission:
        with self.observability.span(
            "durable.submit"
        ):
            conversation, history = (
                self._resolve_conversation(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                )
            )

            run = Run(
                id=new_id("run"),
                conversation_id=conversation.id,
            )
            evidence = RunEvidence()

            safe_input = user_input
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
                run.status = RunStatus.BLOCKED
                run.error_message = (
                    blocking.code
                )
                run.updated_at = utc_now()

                with self.database.uow() as uow:
                    uow.runs.add(run)
                    uow.messages.add_user(
                        conversation_id=conversation.id,
                        content=(
                            "[BLOCKED_INPUT_OMITTED]"
                        ),
                    )
                    uow.messages.add_assistant(
                        conversation_id=conversation.id,
                        content=(
                            "请求被安全策略阻止。"
                        ),
                    )
                    uow.events.add(
                        RuntimeEvent(
                            id=new_id("evt"),
                            run_id=run.id,
                            event_type="run.blocked",
                            payload={
                                "security_code": (
                                    blocking.code
                                )
                            },
                        )
                    )
                    uow.commit()

                self.security.finish_run(
                    run.id
                )

                return DurableSubmission(
                    conversation_id=conversation.id,
                    run_id=run.id,
                    status=DurableRunStatus.FAILED,
                    blocked=True,
                    output="请求被安全策略阻止。",
                )

            run.status = RunStatus.PENDING
            run.updated_at = utc_now()

            with self.database.uow() as uow:
                uow.runs.add(run)
                uow.messages.add_user(
                    conversation_id=conversation.id,
                    content=safe_input,
                )
                uow.events.add(
                    RuntimeEvent(
                        id=new_id("evt"),
                        run_id=run.id,
                        event_type="run.submitted",
                        payload={},
                    )
                )
                uow.commit()

            execution = (
                self.runner.create_execution(
                    safe_input,
                    history=history,
                    external_context=external_context,
                    tool_context=ToolContext(
                        run_id=run.id,
                        workspace_id=workspace_id,
                        workspace_path=workspace_path,
                        knowledge_path=knowledge_path,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        permissions=permissions,
                        tool_names=tool_names,
                    ),
                    working_state=WorkingState(
                        goal=safe_input
                    ),
                )
            )
            execution.evidence.security_decisions.extend(
                evidence.security_decisions
            )

            with self.database.uow() as uow:
                uow.checkpoints.add(Checkpoint(id=new_id("cp"), run_id=run.id, step_sequence=0, state=execution_to_dict(execution)))
                uow.commit()
            self.durable_store.enqueue(
                run_id=run.id,
                execution=execution,
                trace_carrier=(
                    inject_current_context()
                ),
            )

            self._emit(
                run.id,
                {
                    "type": "run.submitted",
                    "conversation_id": conversation.id,
                    "input": safe_input,
                },
            )

            return DurableSubmission(
                conversation_id=conversation.id,
                run_id=run.id,
                status=DurableRunStatus.PENDING,
            )

    def get_result(
        self,
        run_id: str,
    ) -> DurableResult:
        durable = (
            self.durable_store.get(
                run_id
            )
        )
        if durable is None:
            raise ValueError(
                f"durable run not found: {run_id}"
            )

        with self.database.uow() as uow:
            run = uow.runs.get(
                run_id
            )

        if run is None:
            raise ValueError(
                f"run not found: {run_id}"
            )

        call = (
            durable.execution.current_tool_call
        )

        return DurableResult(
            conversation_id=(
                run.conversation_id
            ),
            run_id=run_id,
            status=durable.status,
            output=(
                durable.execution.final_output
            ),
            waiting_call_id=(
                call.call_id
                if call
                else None
            ),
            waiting_tool_name=(
                call.name
                if call
                else None
            ),
            error_message=(
                durable.execution.error_message
            ),
        )

    def approve(
        self,
        *,
        run_id: str,
        approved_by: str,
    ) -> None:
        record = (
            self.durable_store.get(
                run_id
            )
        )
        if record is None:
            raise ValueError(
                f"durable run not found: {run_id}"
            )

        call = (
            record.execution.current_tool_call
        )
        if (
            record.execution.phase
            != ExecutionPhase.WAITING_APPROVAL
            or call is None
        ):
            raise ValueError(
                "run is not waiting for approval"
            )

        self.approval_store.approve(
            run_id=run_id,
            call_id=call.call_id,
            tool_name=call.name,
            approved_by=approved_by,
        )
        self.durable_store.wake_after_approval(
            run_id=run_id
        )

        with self.database.uow() as uow:
            run = uow.runs.get(
                run_id
            )
            if run is not None:
                run.status = (
                    RunStatus.PENDING
                )
                run.updated_at = utc_now()
                uow.runs.update(run)
                uow.events.add(
                    RuntimeEvent(
                        id=new_id("evt"),
                        run_id=run_id,
                        event_type="run.approved",
                        payload={
                            "tool_name": call.name,
                            "call_id": call.call_id,
                            "approved_by": approved_by,
                        },
                    )
                )
                uow.commit()

    def cancel(
        self,
        *,
        run_id: str,
    ) -> None:
        self.durable_store.request_cancel(
            run_id=run_id
        )

    def prepare_completed(
        self,
        state,
    ) -> None:
        """最终 Output 在进入 Durable/Persistence 前经过 Phase 9 Guardrail。"""
        safe_output = (
            state.final_output
            or ""
        )
        (
            safe_output,
            decisions,
        ) = self.security.inspect_output(
            text=safe_output,
            run_id=state.run_id,
        )

        for decision in decisions:
            state.evidence.security_decisions.append(
                SecurityDecisionRecord(
                    stage="output",
                    action=decision.action.value,
                    code=decision.code,
                )
            )

        blocking = next(
            (
                item
                for item in decisions
                if item.action
                == SecurityAction.BLOCK
            ),
            None,
        )
        state.final_output = (
            "响应被安全策略阻止。"
            if blocking
            else safe_output
        )

    def persist_transition(
        self,
        *,
        state,
        previous_phase: ExecutionPhase,
    ) -> None:
        """每个 Durable Transition 同步回 Phase 4 Step / Checkpoint / Event。"""
        step_type = (
            StepType.MODEL
            if previous_phase
            == ExecutionPhase.MODEL
            else StepType.TOOL
        )
        step_status = (
            StepStatus.WAITING
            if state.phase
            in {
                ExecutionPhase.WAITING_APPROVAL,
                ExecutionPhase.WAITING_RECONCILIATION,
            }
            else StepStatus.COMPLETED
        )

        with self.database.uow() as uow:
            run = uow.runs.get(
                state.run_id
            )
            if run is None:
                raise ValueError(
                    f"run not found: {state.run_id}"
                )

            run.current_step = (
                state.transition_count
            )
            run.status = (
                RunStatus.WAITING
                if step_status
                == StepStatus.WAITING
                else RunStatus.RUNNING
            )
            run.provider_response_id = (
                state.previous_response_id
            )
            run.updated_at = utc_now()

            step = Step(
                id=new_id("step"),
                run_id=state.run_id,
                sequence=(
                    state.transition_count
                ),
                type=step_type,
                status=step_status,
                input_data={
                    "phase_before": (
                        previous_phase.value
                    )
                },
                output_data={
                    **state.transition_data,
                    "phase_after": (
                        state.phase.value
                    ),
                    "model_step": (
                        state.model_step
                    ),
                },
            )

            checkpoint = Checkpoint(
                id=new_id("cp"),
                run_id=state.run_id,
                step_sequence=(
                    state.transition_count
                ),
                state=execution_to_dict(
                    state
                ),
            )

            uow.steps.add(step)
            uow.runs.update(run)
            uow.checkpoints.add(
                checkpoint
            )
            uow.events.add(
                RuntimeEvent(
                    id=new_id("evt"),
                    run_id=state.run_id,
                    step_id=step.id,
                    event_type=(
                        "durable.transition"
                    ),
                    payload={
                        "before": (
                            previous_phase.value
                        ),
                        "after": (
                            state.phase.value
                        ),
                        "transition_count": (
                            state.transition_count
                        ),
                    },
                )
            )
            uow.commit()

    def persist_completed(
        self,
        state,
    ) -> None:
        with self.database.uow() as uow:
            run = uow.runs.get(
                state.run_id
            )
            if run is None:
                raise ValueError(
                    f"run not found: {state.run_id}"
                )

            run.status = (
                RunStatus.COMPLETED
            )
            run.current_step = (
                state.transition_count
            )
            run.provider_response_id = (
                state.previous_response_id
            )
            run.updated_at = utc_now()

            uow.messages.add_assistant(
                conversation_id=(
                    run.conversation_id
                ),
                content=(
                    state.final_output
                    or ""
                ),
            )
            uow.runs.update(run)
            uow.events.add(
                RuntimeEvent(
                    id=new_id("evt"),
                    run_id=state.run_id,
                    event_type="run.completed",
                    payload={
                        "steps": (
                            state.model_step
                        )
                    },
                )
            )
            uow.commit()

        self.security.finish_run(
            state.run_id
        )

        self._emit(
            state.run_id,
            {
                "type": "run.end",
                "status": "completed",
                "output": state.final_output or "",
                "steps": state.model_step,
                "tokens": (
                    state.evidence.model_usage.total_tokens
                ),
            },
        )

    def persist_waiting(
        self,
        state,
    ) -> None:
        with self.database.uow() as uow:
            run = uow.runs.get(
                state.run_id
            )
            if run is None:
                raise ValueError(
                    f"run not found: {state.run_id}"
                )

            run.status = (
                RunStatus.WAITING
            )
            run.current_step = (
                state.transition_count
            )
            run.updated_at = utc_now()
            uow.runs.update(run)
            uow.events.add(
                RuntimeEvent(
                    id=new_id("evt"),
                    run_id=state.run_id,
                    event_type="run.waiting",
                    payload={
                        "phase": (
                            state.phase.value
                        )
                    },
                )
            )
            uow.commit()

        call = state.current_tool_call
        self._emit(
            state.run_id,
            {
                "type": "run.waiting",
                "phase": state.phase.value,
                "call_id": call.call_id if call else None,
                "tool_name": call.name if call else None,
                "arguments": dict(call.arguments) if call else None,
            },
        )

    def persist_failed(
        self,
        state,
        error: Exception,
    ) -> None:
        state.phase = (
            ExecutionPhase.FAILED
        )
        state.error_message = str(
            error
        )

        with self.database.uow() as uow:
            run = uow.runs.get(
                state.run_id
            )
            if run is not None:
                run.status = (
                    RunStatus.FAILED
                )
                run.error_message = (
                    str(error)
                )
                run.updated_at = (
                    utc_now()
                )
                uow.runs.update(run)
                uow.events.add(
                    RuntimeEvent(
                        id=new_id("evt"),
                        run_id=state.run_id,
                        event_type="run.failed",
                        payload={
                            "error_type": (
                                type(error).__name__
                            )
                        },
                    )
                )
                uow.commit()

        self.security.finish_run(
            state.run_id
        )

        self._emit(
            state.run_id,
            {
                "type": "run.end",
                "status": "failed",
                "output": state.final_output or "",
                "error": state.error_message,
            },
        )

    def persist_cancelled(
        self,
        state,
    ) -> None:
        state.phase = (
            ExecutionPhase.CANCELLED
        )

        with self.database.uow() as uow:
            run = uow.runs.get(
                state.run_id
            )
            if run is not None:
                run.status = (
                    RunStatus.CANCELLED
                )
                run.updated_at = (
                    utc_now()
                )
                uow.runs.update(run)
                uow.events.add(
                    RuntimeEvent(
                        id=new_id("evt"),
                        run_id=state.run_id,
                        event_type="run.cancelled",
                        payload={},
                    )
                )
                uow.commit()

        self.security.finish_run(
            state.run_id
        )

        self._emit(
            state.run_id,
            {
                "type": "run.end",
                "status": "cancelled",
                "output": state.final_output or "",
            },
        )

    def _resolve_conversation(
        self,
        *,
        user_id: str,
        tenant_id: str,
        conversation_id: str | None,
    ):
        if conversation_id is None:
            conversation = Conversation(
                id=new_id("conv"),
                user_id=user_id,
                tenant_id=tenant_id,
            )
            with self.database.uow() as uow:
                uow.conversations.add(
                    conversation
                )
                uow.commit()
            return conversation, []

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
            if (
                conversation.tenant_id
                != tenant_id
            ):
                raise PermissionError(
                    "conversation tenant mismatch"
                )

            history = (
                uow.messages.list_recent(
                    conversation_id=(
                        conversation.id
                    ),
                    limit=100,
                )
            )
            return (
                conversation,
                history,
            )
