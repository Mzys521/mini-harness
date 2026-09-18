from harness.evaluation.models import (
    EvalCase,
    EvalSample,
)

class HarnessEvaluationTarget:
    """Adapter（适配器）：让真实 PersistentAgentService 可以被 EvaluationRunner 调用。"""

    def __init__(self, application, user_id: str, tenant_id: str, permissions: frozenset[str]) -> None:
        self.application = application
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.permissions = permissions

    async def run_case(self, case: EvalCase) -> EvalSample:
        # 每个 Eval Case 使用独立 Conversation，避免 Case 互相污染。
        result = await self.application.ask(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            user_input=case.input,
            permissions=self.permissions,
            conversation_id=None,
        )

        return EvalSample(
            case_id=case.id,
            output=result.output,
            steps=result.steps,
            evidence=result.evidence,
            run_id=result.run_id,
        )