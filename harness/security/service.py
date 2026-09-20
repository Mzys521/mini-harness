# 文件：harness/security/service.py
from harness.security.models import (
    SecurityAction,
    SecurityAuditEvent,
    SecurityDecision,
)

class SecurityService:
    """Input / Output / Tool Policy 的统一 Security Facade。"""

    def __init__(
        self,
        *,
        input_guards,
        output_guards,
        tool_policy,
        audit_sink,
        observability,
        metrics,
    ) -> None:
        self.input_guards = list(
            input_guards
        )
        self.output_guards = list(
            output_guards
        )
        self.tool_policy = tool_policy
        self.audit_sink = audit_sink
        self.observability = observability
        self.metrics = metrics

    def inspect_input(
        self,
        *,
        text: str,
        run_id: str,
    ) -> tuple[str, list[SecurityDecision]]:
        current = text
        decisions: list[SecurityDecision] = []

        with self.observability.span(
            "security.input",
            {"agent.run_id": run_id},
        ):
            for guard in self.input_guards:
                decision = guard.inspect(
                    current
                )
                decisions.append(
                    decision
                )
                self._record(
                    event_type="input_guard",
                    run_id=run_id,
                    tool_name=None,
                    decision=decision,
                    metadata={
                        "guard": guard.name
                    },
                )

                if decision.transformed_text is not None:
                    current = decision.transformed_text

                if decision.action == SecurityAction.BLOCK:
                    return current, decisions

        return current, decisions

    def inspect_output(
        self,
        *,
        text: str,
        run_id: str,
    ) -> tuple[str, list[SecurityDecision]]:
        current = text
        decisions: list[SecurityDecision] = []

        with self.observability.span(
            "security.output",
            {"agent.run_id": run_id},
        ):
            for guard in self.output_guards:
                decision = guard.inspect(
                    current
                )
                decisions.append(
                    decision
                )
                self._record(
                    event_type="output_guard",
                    run_id=run_id,
                    tool_name=None,
                    decision=decision,
                    metadata={
                        "guard": guard.name
                    },
                )

                if decision.transformed_text is not None:
                    current = decision.transformed_text

                if decision.action == SecurityAction.BLOCK:
                    return current, decisions

        return current, decisions

    def inspect_tool_result(
        self,
        *,
        text: str,
        run_id: str,
        tool_name: str,
    ) -> tuple[str, list[SecurityDecision]]:
        """外部 Tool Result 在回流模型前也经过安全投影。"""
        current = text
        decisions: list[SecurityDecision] = []

        with self.observability.span(
            "security.tool_result",
            {
                "agent.run_id": run_id,
                "tool.name": tool_name,
            },
        ):
            for guard in self.output_guards:
                decision = guard.inspect(
                    current
                )
                decisions.append(
                    decision
                )
                self._record(
                    event_type="tool_result_guard",
                    run_id=run_id,
                    tool_name=tool_name,
                    decision=decision,
                    metadata={
                        "guard": guard.name
                    },
                )

                if decision.transformed_text is not None:
                    current = decision.transformed_text

                if decision.action == SecurityAction.BLOCK:
                    return (
                        "[TOOL_RESULT_BLOCKED_BY_SECURITY_POLICY]",
                        decisions,
                    )

        return current, decisions

    def authorize_tool(
        self,
        *,
        tool,
        call,
        context,
    ) -> SecurityDecision:
        with self.observability.span(
            "security.tool_policy",
            {
                "agent.run_id": context.run_id,
                "tool.name": tool.name,
            },
        ) as span:
            decision = self.tool_policy.authorize(
                tool=tool,
                call=call,
                context=context,
            )

            span.set_attribute(
                "security.action",
                decision.action.value,
            )
            span.set_attribute(
                "security.code",
                decision.code,
            )

            self._record(
                event_type="tool_policy",
                run_id=context.run_id,
                tool_name=tool.name,
                decision=decision,
                metadata={},
            )
            return decision

    def _record(
        self,
        *,
        event_type: str,
        run_id: str,
        tool_name: str | None,
        decision: SecurityDecision,
        metadata: dict,
    ) -> None:
        self.metrics.security_decisions.add(
            1,
            {
                "event_type": event_type,
                "action": decision.action.value,
                "code": decision.code,
            },
        )

        if decision.action in {
            SecurityAction.BLOCK,
            SecurityAction.APPROVAL_REQUIRED,
        }:
            self.metrics.security_blocks.add(
                1,
                {
                    "event_type": event_type,
                    "code": decision.code,
                },
            )

        if decision.action == SecurityAction.REDACT:
            self.metrics.security_redactions.add(
                1,
                {
                    "event_type": event_type,
                    "code": decision.code,
                },
            )

        self.audit_sink.emit(
            SecurityAuditEvent(
                event_type=event_type,
                action=decision.action.value,
                code=decision.code,
                reason=decision.reason,
                run_id=run_id,
                tool_name=tool_name,
                metadata=metadata,
            )
        )

    def finish_run(
        self,
        run_id: str,
    ) -> None:
        """允许 Policy 清理 Run-scoped（运行级）临时状态。"""
        finish = getattr(
            self.tool_policy,
            "finish_run",
            None,
        )
        if finish is not None:
            finish(run_id)