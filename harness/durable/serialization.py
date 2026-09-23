# 文件：harness/durable/serialization.py
from typing import Any

from harness.durable.models import (
    AgentExecutionState,
    ExecutionPhase,
)
from harness.models import (
    ModelUsage,
    RunEvidence,
    SecurityDecisionRecord,
    ToolCall,
    ToolExecutionRecord,
)
from harness.tools.definition import (
    ToolContext,
)

def execution_to_dict(
    state: AgentExecutionState,
) -> dict[str, Any]:
    return {
        "run_id": state.run_id,
        "user_input": state.user_input,
        "instructions": state.instructions,
        "current_input": state.current_input,
        "tool_context": {
            "run_id": state.tool_context.run_id,
            "workspace_id": state.tool_context.workspace_id,
            "workspace_path": state.tool_context.workspace_path,
            "knowledge_path": state.tool_context.knowledge_path,
            "user_id": state.tool_context.user_id,
            "tenant_id": state.tool_context.tenant_id,
            "permissions": sorted(
                state.tool_context.permissions
            ),
            "tool_names": (
                None
                if state.tool_context.tool_names is None
                else sorted(
                    state.tool_context.tool_names
                )
            ),
        },
        "phase": state.phase.value,
        "model_step": state.model_step,
        "transition_count": state.transition_count,
        "previous_response_id": (
            state.previous_response_id
        ),
        "pending_tool_calls": [
            {
                "call_id": item.call_id,
                "name": item.name,
                "arguments": item.arguments,
            }
            for item in state.pending_tool_calls
        ],
        "pending_tool_index": (
            state.pending_tool_index
        ),
        "tool_outputs": state.tool_outputs,
        "evidence": {
            "tool_executions": [
                {
                    "call_id": item.call_id,
                    "name": item.name,
                    "arguments": item.arguments,
                    "status": item.status,
                    "error_code": item.error_code,
                    "security_code": (
                        item.security_code
                    ),
                }
                for item in state.evidence.tool_executions
            ],
            "security_decisions": [
                {
                    "stage": item.stage,
                    "action": item.action,
                    "code": item.code,
                }
                for item in state.evidence.security_decisions
            ],
            "model_usage": {
                "input_tokens": (
                    state.evidence.model_usage.input_tokens
                ),
                "output_tokens": (
                    state.evidence.model_usage.output_tokens
                ),
                "total_tokens": (
                    state.evidence.model_usage.total_tokens
                ),
                "cached_input_tokens": (
                    state.evidence.model_usage.cached_input_tokens
                ),
            },
        },
        "final_output": state.final_output,
        "transition_data": state.transition_data,
        "applied_instructions": state.applied_instructions,
        "error_message": state.error_message,
    }

def execution_from_dict(
    data: dict[str, Any],
) -> AgentExecutionState:
    tool_context_data = data[
        "tool_context"
    ]
    evidence_data = data.get(
        "evidence",
        {},
    )
    usage_data = evidence_data.get(
        "model_usage",
        {},
    )

    evidence = RunEvidence(
        tool_executions=[
            ToolExecutionRecord(
                call_id=item["call_id"],
                name=item["name"],
                arguments=dict(
                    item.get(
                        "arguments",
                        {},
                    )
                ),
                status=item["status"],
                error_code=item.get(
                    "error_code"
                ),
                security_code=item.get(
                    "security_code"
                ),
            )
            for item in evidence_data.get(
                "tool_executions",
                [],
            )
        ],
        security_decisions=[
            SecurityDecisionRecord(
                stage=item["stage"],
                action=item["action"],
                code=item["code"],
            )
            for item in evidence_data.get(
                "security_decisions",
                [],
            )
        ],
        model_usage=ModelUsage(
            input_tokens=int(
                usage_data.get(
                    "input_tokens",
                    0,
                )
            ),
            output_tokens=int(
                usage_data.get(
                    "output_tokens",
                    0,
                )
            ),
            total_tokens=int(
                usage_data.get(
                    "total_tokens",
                    0,
                )
            ),
            cached_input_tokens=int(
                usage_data.get(
                    "cached_input_tokens",
                    0,
                )
            ),
        ),
    )

    return AgentExecutionState(
        run_id=data["run_id"],
        user_input=data["user_input"],
        instructions=data["instructions"],
        current_input=list(
            data.get(
                "current_input",
                [],
            )
        ),
        tool_context=ToolContext(
            workspace_id=tool_context_data.get("workspace_id"),
            workspace_path=tool_context_data.get(
                "workspace_path"
            ),
            knowledge_path=tool_context_data.get(
                "knowledge_path"
            ),
            run_id=tool_context_data[
                "run_id"
            ],
            user_id=tool_context_data.get(
                "user_id"
            ),
            tenant_id=tool_context_data.get(
                "tenant_id"
            ),
            permissions=frozenset(
                tool_context_data.get(
                    "permissions",
                    [],
                )
            ),
            tool_names=(
                None
                if tool_context_data.get(
                    "tool_names"
                )
                is None
                else frozenset(
                    tool_context_data["tool_names"]
                )
            ),
        ),
        phase=ExecutionPhase(
            data.get(
                "phase",
                ExecutionPhase.MODEL.value,
            )
        ),
        model_step=int(
            data.get(
                "model_step",
                0,
            )
        ),
        transition_count=int(
            data.get(
                "transition_count",
                0,
            )
        ),
        previous_response_id=data.get(
            "previous_response_id"
        ),
        pending_tool_calls=[
            ToolCall(
                call_id=item["call_id"],
                name=item["name"],
                arguments=dict(
                    item.get(
                        "arguments",
                        {},
                    )
                ),
            )
            for item in data.get(
                "pending_tool_calls",
                [],
            )
        ],
        pending_tool_index=int(
            data.get(
                "pending_tool_index",
                0,
            )
        ),
        tool_outputs=list(
            data.get(
                "tool_outputs",
                [],
            )
        ),
        evidence=evidence,
        final_output=data.get(
            "final_output"
        ),
        transition_data=data.get("transition_data", {}),
        applied_instructions=data.get("applied_instructions", []),
        error_message=data.get(
            "error_message"
        ),
    )
