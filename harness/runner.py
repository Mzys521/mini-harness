# 文件：harness/runner.py
from dataclasses import replace
from time import perf_counter
from typing import Any, Callable

from harness.context.models import (
    WorkingState,
)
from harness.durable.models import (
    AgentExecutionState,
    ExecutionPhase,
)
from harness.models import (
    ModelUsage,
    RunEvidence,
    RunResult,
    SecurityDecisionRecord,
    ToolExecutionRecord,
)
from harness.streaming import accepts_keyword
from harness.tools.result import (
    ToolStatus,
)

class AgentRunner:
    """Phase 10：同一核心同时支持 Immediate Mode 与 Durable State Machine。"""

    def __init__(
        self,
        *,
        model,
        registry,
        executor,
        context_builder,
        observability,
        system_instruction: str,
        max_steps: int | None = None,
        emitter: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self.model = model
        self.registry = registry
        self.executor = executor
        self.context_builder = context_builder
        self.observability = observability
        self.system_instruction = (
            system_instruction
        )
        self.max_steps = max_steps
        # 事件出口（通常是 RunEventBroker.publish）；为 None 时退化为纯批处理。
        self.emitter = emitter
        # 旧 Provider 的 generate() 没有 on_delta，探测一次即可保持向后兼容。
        self.supports_streaming = emitter is not None and accepts_keyword(
            getattr(model, "generate", None),
            "on_delta",
        )

    def _emit(self, run_id: str, event: dict[str, Any]) -> None:
        if self.emitter is not None:
            self.emitter(run_id, event)

    def create_execution(
        self,
        user_input: str,
        *,
        history: list,
        tool_context,
        working_state: WorkingState | None = None,
        retrieved_context: str | None = None,
        external_context: str | None = None,
    ) -> AgentExecutionState:
        """把 Model Context 投影为可序列化的初始执行状态。"""
        # 能力快照：本次 Run 能看到哪些工具，在创建时就固定下来并进入 Durable 状态。
        # 因此运行期登记的工具（MCP Server）只影响之后新建的 Run，已在跑的 Run
        # 既不会被授予新能力，崩溃恢复后也仍按原快照执行。
        if tool_context.tool_names is None:
            tool_context = replace(
                tool_context,
                tool_names=frozenset(
                    tool.name
                    for tool in self.registry.list_tools()
                ),
            )

        state = (
            working_state
            or WorkingState(
                goal=user_input
            )
        )
        context = (
            self.context_builder.build(
                system_instruction=(
                    self.system_instruction
                ),
                history=history,
                user_input=user_input,
                working_state=state,
                retrieved_context=retrieved_context,
                external_context=external_context,
            )
        )

        return AgentExecutionState(
            run_id=tool_context.run_id,
            user_input=user_input,
            instructions=context.instructions,
            current_input=context.input_data,
            tool_context=tool_context,
        )

    async def advance(
        self,
        state: AgentExecutionState,
        *,
        pause_on_approval: bool = True,
    ) -> AgentExecutionState:
        """只执行一个可持久化 Transition（状态转换）。

        Worker 每调用一次 advance() 后都可以把 state 落库，因此进程崩溃时
        最多丢失当前 Transition，而不是整个 Agent Run。
        """
        if state.phase in {
            ExecutionPhase.COMPLETED,
            ExecutionPhase.FAILED,
            ExecutionPhase.CANCELLED,
            ExecutionPhase.WAITING_APPROVAL,
            ExecutionPhase.WAITING_RECONCILIATION,
        }:
            return state

        if (
            state.phase
            == ExecutionPhase.MODEL
        ):
            advanced = await self._advance_model(
                state
            )
        elif (
            state.phase
            == ExecutionPhase.TOOL
        ):
            advanced = await self._advance_tool(
                state,
                pause_on_approval=(
                    pause_on_approval
                ),
            )
        else:
            raise RuntimeError(
                "unknown execution phase: "
                f"{state.phase}"
            )

        self._emit(
            advanced.run_id,
            {
                "type": "phase",
                "phase": advanced.phase.value,
                "transition": advanced.transition_count,
            },
        )
        return advanced

    async def _advance_model(
        self,
        state: AgentExecutionState,
    ) -> AgentExecutionState:
        step = state.model_step + 1
        self._emit(state.run_id, {"type": "model.start", "step": step})

        def on_delta(text: str) -> None:
            self._emit(
                state.run_id,
                {"type": "model.delta", "step": step, "text": text},
            )

        streaming_kwargs = {"on_delta": on_delta} if self.supports_streaming else {}

        started = perf_counter()
        with self.observability.span(
            "agent.model_transition",
            {
                "agent.run_id": state.run_id,
                "agent.next_step": (
                    state.model_step + 1
                ),
            },
        ):
            model_result = (
                await self.model.generate(
                    input_data=(
                        state.current_input
                    ),
                    instructions=(
                        state.instructions
                    ),
                    tools=(
                        self.registry.openai_schemas(
                            state.tool_context.tool_names
                        )
                    ),
                    previous_response_id=(
                        state.previous_response_id
                    ),
                    **streaming_kwargs,
                )
            )

        # 单次模型请求快照：耗时包括首字等待，不包含工具和审批等待。
        usage = model_result.usage
        budget = getattr(self.context_builder, "budget", None)
        metrics = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "cached_input_tokens": (
                usage.cached_input_tokens if model_result.cache_usage_reported else None
            ),
            "duration_ms": (perf_counter() - started) * 1000,
            "context_window": getattr(budget, "max_context_tokens", None),
        }
        state.model_step += 1
        state.transition_data = {
            "name": "模型响应", "input": state.current_input,
            "output": model_result.text,
            "tokens": model_result.usage.total_tokens,
            "metrics": metrics,
            "calls": [{"name": c.name, "arguments": c.arguments} for c in model_result.tool_calls],
        }
        state.transition_count += 1
        state.previous_response_id = (
            model_result.response_id
        )
        state.evidence.model_usage = (
            state.evidence.model_usage
            + model_result.usage
        )

        self._emit(
            state.run_id,
            {
                "type": "model.end",
                "step": state.model_step,
                "text": model_result.text,
                "tokens": model_result.usage.total_tokens,
                "metrics": metrics,
                "tool_calls": [
                    {
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": dict(call.arguments),
                    }
                    for call in model_result.tool_calls
                ],
            },
        )

        if not model_result.tool_calls:
            state.final_output = (
                model_result.text
            )
            state.phase = (
                ExecutionPhase.COMPLETED
            )
            return state

        state.pending_tool_calls = list(
            model_result.tool_calls
        )
        state.pending_tool_index = 0
        state.tool_outputs = []
        state.phase = (
            ExecutionPhase.TOOL
        )
        return state

    async def _advance_tool(
        self,
        state: AgentExecutionState,
        *,
        pause_on_approval: bool,
    ) -> AgentExecutionState:
        call = state.current_tool_call

        if call is None:
            # 当前 Batch 的 Tool 已全部完成，把结果交回 Model。
            state.current_input = list(
                state.tool_outputs
            )
            state.pending_tool_calls = []
            state.pending_tool_index = 0
            state.tool_outputs = []
            state.phase = (
                ExecutionPhase.MODEL
            )
            return state

        self._emit(
            state.run_id,
            {
                "type": "tool.start",
                "call_id": call.call_id,
                "name": call.name,
                "arguments": dict(call.arguments),
            },
        )

        tool_result = (
            await self.executor.execute(
                call,
                state.tool_context,
            )
        )
        state.transition_count += 1

        self._emit(
            state.run_id,
            {
                "type": "tool.end",
                "call_id": call.call_id,
                "name": call.name,
                "status": tool_result.status.value,
                "output": tool_result.to_model_output(),
                "error_code": tool_result.error_code,
                "security_code": tool_result.security_code,
            },
        )

        state.evidence.tool_executions.append(
            ToolExecutionRecord(
                call_id=call.call_id,
                name=call.name,
                arguments=dict(
                    call.arguments
                ),
                status=(
                    tool_result.status.value
                ),
                error_code=(
                    tool_result.error_code
                ),
                security_code=(
                    tool_result.security_code
                ),
            )
        )
        state.transition_data = {
            "name": call.name, "input": call.arguments,
            "output": tool_result.to_model_output(), "tokens": 0,
            "status": tool_result.status.value,
            "error_code": tool_result.error_code,
            "call_id": call.call_id,
        }

        for security_code in (
            tool_result.security_codes
        ):
            state.evidence.security_decisions.append(
                SecurityDecisionRecord(
                    stage=(
                        "tool"
                        if security_code
                        in {
                            "SEC_APPROVAL_REQUIRED",
                            "SEC_TOOL_DISABLED",
                            "SEC_TOOL_BUDGET_EXCEEDED",
                        }
                        else "tool_result"
                    ),
                    action=(
                        tool_result.status.value
                    ),
                    code=security_code,
                )
            )

        if (
            tool_result.status
            == ToolStatus.APPROVAL_REQUIRED
            and pause_on_approval
        ):
            # pending_tool_index 不前进；审批后恢复的是同一个 call_id。
            state.phase = (
                ExecutionPhase.WAITING_APPROVAL
            )
            return state

        if (
            tool_result.status
            == ToolStatus.RECONCILIATION_REQUIRED
            and pause_on_approval
        ):
            state.phase = (
                ExecutionPhase.WAITING_RECONCILIATION
            )
            return state

        state.tool_outputs.append({
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": (
                tool_result.to_model_output()
            ),
        })
        state.pending_tool_index += 1

        if (
            state.pending_tool_index
            >= len(
                state.pending_tool_calls
            )
        ):
            state.current_input = list(
                state.tool_outputs
            )
            state.pending_tool_calls = []
            state.pending_tool_index = 0
            state.tool_outputs = []
            state.phase = (
                ExecutionPhase.MODEL
            )

        return state

    def resume_after_approval(
        self,
        state: AgentExecutionState,
    ) -> AgentExecutionState:
        if (
            state.phase
            != ExecutionPhase.WAITING_APPROVAL
        ):
            return state

        state.phase = (
            ExecutionPhase.TOOL
        )
        return state

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
        """Phase 1–9 兼容入口：仍然可以一次 await 跑完整 Agent。

        Immediate Mode 不暂停等待人工审批，而是把 APPROVAL_REQUIRED ToolResult
        反馈给模型，让模型告诉用户“需要审批”。真正长时间等待由 Durable Mode 负责。
        """
        with self.observability.span(
            "agent.loop",
            {
                "agent.max_steps": (
                    self.max_steps
                )
            },
        ) as span:
            state = self.create_execution(
                user_input,
                history=history,
                tool_context=tool_context,
                working_state=working_state,
                retrieved_context=retrieved_context,
                external_context=external_context,
            )

            while state.phase not in {
                ExecutionPhase.COMPLETED,
                ExecutionPhase.FAILED,
                ExecutionPhase.CANCELLED,
            }:
                # Immediate Mode 不进入长时间 WAITING。
                if state.phase in {
                    ExecutionPhase.WAITING_APPROVAL,
                    ExecutionPhase.WAITING_RECONCILIATION,
                }:
                    state.phase = (
                        ExecutionPhase.TOOL
                    )

                state = await self.advance(
                    state,
                    pause_on_approval=False,
                )

            span.set_attribute(
                "agent.steps",
                state.model_step,
            )

            if (
                state.phase
                != ExecutionPhase.COMPLETED
            ):
                raise RuntimeError(
                    state.error_message
                    or (
                        "agent did not complete: "
                        f"{state.phase}"
                    )
                )

            return RunResult(
                output=(
                    state.final_output
                    or ""
                ),
                steps=state.model_step,
                response_id=(
                    state.previous_response_id
                ),
                evidence=state.evidence,
            )
