from mcp.types import ToolExecution

from harness.context.models import WorkingState
from harness.models import RunResult , RunEvidence , ModelUsage, ToolExecutionRecord
from harness.tools.definition import ToolContext


class AgentRunner:
    """Agent 主循环驱动器: 模型生成 -> 执行工具 -> 回传结果，直至无工具调用或达到步数上限"""

    def __init__(self, * , model , registry , executor , context_builder , system_instruction : str , max_steps:int = 8 , observability) -> None:
        self.model = model
        self.registry = registry
        self.executor = executor
        self.context_builder = context_builder
        self.system_instruction = system_instruction
        self.max_steps = max_steps
        self.observability = observability

    async def run(
        self,
        user_input: str,
        *,
        history: list,
        tool_context,
        working_state: WorkingState | None = None,
        retrieved_context: str | None = None,
        external_context: str | None = None,
    ) -> RunResult:
        """
        AgentRunner（智能体运行器）的公共入口。

        Phase 7（阶段7）以后：
        run() 只负责 agent.loop Span（智能体循环跨度），
        真正 Agent Loop（智能体循环）交给 _run_loop()。
        """

        with self.observability.span(
            "agent.loop",
            {
                "agent.max_steps": self.max_steps,
            },
        ) as span:

            result = await self._run_loop(
                user_input,
                history=history,
                tool_context=tool_context,
                working_state=working_state,
                retrieved_context=retrieved_context,
                external_context=external_context,
            )

            # 把最终实际执行 Step（步骤）数量写入 Span（跨度）。
            span.set_attribute(
                "agent.steps",
                result.steps,
            )

            return result

    async def _run_loop(
        self,
        user_input: str,
        *,
        history: list,
        tool_context: ToolContext,
        working_state: WorkingState | None = None,
        retrieved_context: str | None = None,
        external_context: str | None = None,
    ) -> RunResult:
        state = working_state or WorkingState(goal=user_input)

        context = self.context_builder.build(
            system_instruction=self.system_instruction,
            history=history,
            user_input=user_input,
            working_state=state,
            retrieved_context=retrieved_context,
            external_context=external_context,
        )

        current_input = context.input_data
        previous_response_id = None

        evidence = RunEvidence()
        total_usage = ModelUsage()

        for step in range(1, self.max_steps + 1):
            model_result = await self.model.generate(
                input_data=current_input,
                instructions=(context.instructions if previous_response_id is None else None),
                tools=self.registry.openai_schemas(),
                previous_response_id=previous_response_id,
            )

            previous_response_id = model_result.response_id

            if not model_result.tool_calls:
                evidence.model_usage = total_usage

                return RunResult(
                    output=model_result.text,
                    steps=step,
                    response_id=previous_response_id,
                    evidence=evidence,
                )

            tool_outputs = []

            for call in model_result.tool_calls:
                result = await self.executor.execute(
                    call,
                    tool_context,
                )

                # 保存应用事实， 而不是让Evaluation 去读取 Trace Backend
                evidence.tool_executions.append(
                    ToolExecutionRecord(
                        call_id = call.call_id,
                        name = call.name,
                        arguments = dict(call.arguments),
                        status = result.status.value,
                        error_code = result.error_code,
                    )
                )

                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result.to_model_output(),
                })

            current_input = tool_outputs

        raise RuntimeError(
            f"agent exceeded max_steps={self.max_steps}"
        )

