from typing import Protocol

from harness.evaluation.models import (
    EvalCase,
    EvalSample,
    EvalScore,
)

class Evaluator(Protocol):
    """所有 Evaluator（评估器）共同遵守的最小接口"""

    @property
    def name(self) -> str:...

    def applies_to(self,case: EvalCase,) -> bool:...

    async def evaluate(self,case: EvalCase,sample: EvalSample,) -> EvalScore:...

class EvaluationTarget(Protocol):
    """Evaluation Runner（评估运行器）不直接依赖 PersistentAgentService。"""

    async def run_case(self, case: EvalCase,) -> EvalSample:... 