import logging

from time import perf_counter
from harness.context.models import WorkingState
from harness.models import RunEvidence
from harness.state.ids import new_id
from harness.state.models import Conversation, Run, RunStatus, utc_now ,RunState , Checkpoint
from harness.tools.definition import ToolContext
from dataclasses import dataclass , field , asdict

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ApplicationResult:
    conversation_id: str
    run_id: str
    output: str
    steps: int
    evidence: RunEvidence = field(default_factory=RunEvidence)


class PersistentAgentService:
    """协调 Persistence（持久化）与 AgentRunner（智能体运行器）。"""

    def __init__(self, *, runner, database , observability , metrics) -> None:
        self.runner = runner
        self.database = database
        self.observability = observability
        self.metrics = metrics

    async def ask(
        self,
        *,
        user_id: str,
        tenant_id: str,
        user_input: str,
        permissions: frozenset[str],
        conversation_id: str | None = None,
    )-> ApplicationResult:

        started = perf_counter()

        if conversation_id is None:
            conversation = Conversation(
                id=new_id("conv"),
                user_id=user_id,
                tenant_id=tenant_id,
            )
            history = []

            with self.database.uow() as uow:
                uow.conversations.add(conversation)
                uow.commit()
        else:
            with self.database.uow() as uow:
                conversation = uow.conversations.get(conversation_id)
                if conversation is None:
                    raise ValueError("conversation not found")
                if conversation.tenant_id != tenant_id:
                    raise PermissionError("conversation tenant mismatch")
                history = uow.messages.list_recent(
                    conversation_id=conversation.id,
                    limit=100,
                )

        run = Run(
            id=new_id("run"),
            conversation_id=conversation.id,
        )

        working_state = WorkingState(goal=user_input)

        self.metrics.agent_runs.add(1 , {"operation": "ask"})

        with self.observability.span(
            "agent.run",
            {
                "agent.run_id": run.id,
            }
        ) as span:
            try : 

                # 第一次事务：先把“任务已经存在”持久化。
                with self.database.uow() as uow:
                    uow.runs.add(run)
                    uow.messages.add_user(
                        conversation_id=conversation.id,
                        content=user_input,
                    )
                    uow.commit()

                run.status = RunStatus.RUNNING
                run.updated_at = utc_now()

                with self.database.uow() as uow:
                    uow.runs.update(run)
                    uow.commit()

                result = await self.runner.run(
                    user_input,
                    history=history,
                    tool_context=ToolContext(
                        run_id=run.id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        permissions=permissions,
                    ),
                    working_state=WorkingState(
                        goal=user_input
                    ),
                )

                run.status = RunStatus.COMPLETED
                run.provider_response_id = result.response_id
                run.updated_at = utc_now()

                checkpoint = Checkpoint(
                    id = new_id("cp"),
                    run_id = run.id,
                    step_sequence= result.steps,
                    state ={
                        "working_state" : asdict(working_state),
                        "provider_response_id" : result.response_id,
                        "final_output" : result.output
                    },
                    created_at = utc_now()
                )

                with self.database.uow() as uow:
                    uow.messages.add_assistant(
                        conversation_id=conversation.id,
                        content=result.output,
                    )
                    uow.runs.update(run)
                    uow.checkpoints.add(checkpoint)
                    uow.commit()
                
                duration = perf_counter() - started
                span.set_attribute("agent.steps", result.steps)
                span.set_attribute("agent.status", "completed")
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
                    },
                )

                return ApplicationResult(
                    conversation_id=conversation.id,
                    run_id=run.id,
                    output=result.output,
                    steps=result.steps,
                    evidence=result.evidence,
                )

            except Exception as exc:
                run.status = RunStatus.FAILED
                run.updated_at = utc_now()

                try : 
                    with self.database.uow() as uow:
                        uow.runs.update(run)
                        uow.commit()
                except Exception :
                    logger.exception(
                        "failed to persist run failure",
                        extra={
                            "run_id" : run.id
                        },
                    )
                self.metrics.agent_errors.add(
                    1, 
                    {"status": "failed"},
                )

                span.set_attribute("agent.status", "failed")

                logger.exception(
                    "agent run failed",
                    extra={
                        "run_id" : run.id
                    }
                )

                raise