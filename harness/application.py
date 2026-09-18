import logging

from time import perf_counter
from harness.context.models import WorkingState
from harness.state.ids import new_id
from harness.state.models import Conversation, Run, RunStatus, utc_now
from harness.tools.definition import ToolContext
from dataclasses import dataclass

@dataclass(frozen=True)
class ApplicationResult:
    conversation_id: str
    run_id: str
    output: str
    steps: int


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
    ):
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

        try:
            result = await self.runner.run(
                user_input,
                tool_context=ToolContext(
                    run_id=run.id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    permissions=permissions,
                ),
                working_state=WorkingState(
                    goal=user_input
                ),
                history=history,
            )

            run.status = RunStatus.COMPLETED
            run.provider_response_id = result.response_id
            run.updated_at = utc_now()

            with self.database.uow() as uow:
                uow.messages.add_assistant(
                    conversation_id=conversation.id,
                    content=result.output,
                )
                uow.runs.update(run)
                uow.commit()

            return ApplicationResult(
                conversation_id=conversation.id,
                run_id=run.id,
                output=result.output,
                steps=result.steps,
            )

        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error_message = str(exc)
            run.updated_at = utc_now()

            with self.database.uow() as uow:
                uow.runs.update(run)
                uow.commit()

            raise