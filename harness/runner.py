from harness.context.models import WorkingState
from harness.models import RunResult
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
        
    # 已于0.6.0版本中弃用
    # -----------------------------------------------------------------------
# @dataclass
# class RunResult:
#     """Agent 一次完整运行的最终结果"""
#     output:str    # 最终文本输出
#     steps:int     # 实际消耗的循环步数

    # def __init__(self, *, model, registry: ToolRegistry, executor : ToolExecutor, max_steps:int = 8) -> None:
    #     """初始化运行器。
    #     参数 model: 模型提供方(需实现 generate 方法)
    #     参数 registry: 工具注册表(提供工具 schema)
    #     参数 executor: 工具执行器(负责参数校验/权限/重试)
    #     参数 max_steps: 最大循环步数，防止死循环
    #     """
    #     self.model = model
    #     self.registry = registry
    #     self.executor = executor
    #     self.max_steps = max_steps

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

        for step in range(1, self.max_steps + 1):
            model_result = await self.model.generate(
                input_data=current_input,
                instructions=context.instructions if previous_response_id is None else None,
                tools=self.registry.openai_schemas(),
                previous_response_id=previous_response_id,
            )

            previous_response_id = model_result.response_id

            if not model_result.tool_calls:
                return RunResult(
                    output=model_result.text,
                    steps=step,
                    response_id=previous_response_id,
                )

            tool_outputs = []

            for call in model_result.tool_calls:
                result = await self.executor.execute(
                    call,
                    tool_context,
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
    # 已于0.6.0版本中弃用

    # -----------------------------------------------------------------------
    # async def run(self , user_input: str , * , context: ToolContext) -> RunResult:
    #     """运行 Agent 主循环。
    #     参数 user_input: 用户本轮的输入文本
    #     参数 context: 工具执行上下文(run_id/用户/权限)
    #     返回: RunResult(最终输出 + 步数)
    #     异常: 超过 max_steps 仍未得到最终答案时抛 RuntimeError
    #     """
    #     current_input = user_input
    #     previous_response_id = None

    #     for step in range(1 , self.max_steps + 1):

    #         # 生成工具调用结果
    #         result = self.model.generate(
    #             input_data = current_input,
    #             tools = self.registry.openai_schema(),
    #             previous_response_id = previous_response_id,
    #         )

    #         # 更新上一个响应的ID
    #         previous_response_id = result.response_id

    #         # 如果没有工具调用，则返回结果
    #         if not result.tool_calls:
    #             return RunResult(
    #                 output = result.text,
    #                 steps = step,
    #             )
            
    #         # 执行工具调用
    #         tool_outputs = []

    #         for call in result.tool_calls:

    #             result = await self.executor.execute(call , context)

    #             tool_outputs.append(
    #                 {
    #                     "type": "function_call_output",
    #                     "call_id": call.call_id,
    #                     "output": result.to_model_output(),
    #                 }
    #             )
            
    #         # 更新当前输入为工具调用输出
    #         current_input = tool_outputs
    #     raise RuntimeError(f"Exceeded max steps ({self.max_steps})")

        

