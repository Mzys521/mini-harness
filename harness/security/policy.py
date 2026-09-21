# 文件：harness/security/policy.py
from harness.security.models import (
    SecurityAction,
    SecurityDecision,
    SecurityFinding,
    SecuritySeverity,
)

class DefaultToolPolicy:
    """LLM Tool Proposal 的最终确定性执行策略。"""

    def __init__(
        self,
        *,
        config,
        approval_store,
        budget_store,
    ) -> None:
        self.config = config
        self.approval_store = approval_store
        self.budget_store = budget_store

    def authorize(
        self,
        *,
        tool,
        call,
        context,
    ) -> SecurityDecision:
        if tool.name in self.config.disabled_tools:
            return SecurityDecision(
                action=SecurityAction.BLOCK,
                code="SEC_TOOL_DISABLED",
                reason=(
                    f"Tool '{tool.name}' 被部署安全策略禁用。"
                ),
                findings=(
                    SecurityFinding(
                        code="SEC_TOOL_DISABLED",
                        severity=SecuritySeverity.HIGH,
                        message="Tool 被管理员安全策略禁用。",
                    ),
                ),
            )

        # 兼容 Phase 6/9：显式字段优先，旧 metadata hint 仍可读取。
        requires_approval = (
            tool.requires_approval
            or bool(
                tool.metadata.get(
                    "requires_approval",
                    False,
                )
            )
            or (
                self.config.approval_required_for_side_effects
                and tool.side_effect
            )
        )

        if requires_approval:
            approved = (
                self.approval_store.is_approved(
                    run_id=context.run_id,
                    call_id=call.call_id,
                    tool_name=tool.name,
                )
            )

            if not approved:
                return SecurityDecision(
                    action=SecurityAction.APPROVAL_REQUIRED,
                    code="SEC_APPROVAL_REQUIRED",
                    reason=(
                        f"Tool '{tool.name}' 具有副作用或策略要求审批，"
                        "当前 Tool Call 尚未获得明确 Approval。"
                    ),
                    findings=(
                        SecurityFinding(
                            code="SEC_APPROVAL_REQUIRED",
                            severity=SecuritySeverity.HIGH,
                            message="高影响 Tool Call 被 Approval Gate 阻止。",
                        ),
                    ),
                )

        return SecurityDecision(
            action=SecurityAction.ALLOW,
            code="SEC_TOOL_ALLOWED",
            reason="Tool Call 通过本地确定性安全策略。",
        )

    def finish_run(
        self,
        run_id: str,
    ) -> None:
        clear = getattr(
            self.budget_store,
            "clear",
            None,
        )
        if clear is not None:
            clear(run_id)
