import asyncio

from harness.evaluation import (
    AnswerContainsEvaluator,
    EvaluationRunner,
    ForbiddenToolEvaluator,
    MaxStepsEvaluator,
    RequiredToolEvaluator,
    assert_quality_gate,
)
from harness.evaluation.models import (
    EvalCase,
    EvalSample,
)
from harness.models import (
    RunEvidence,
    ToolExecutionRecord,
)
from harness.observability.bootstrap import (
    configure_observability,
)
from harness.observability.config import (
    ObservabilityConfig,
)
from harness.observability.metrics import (
    HarnessMetrics,
)
from harness.observability.service import (
    Observability,
)

class SmokeTarget:
    """只验证 Evaluation Pipeline，不依赖真实 Model。"""

    async def run_case(
        self,
        case: EvalCase,
    ) -> EvalSample:
        return EvalSample(
            case_id=case.id,
            output="计算结果是 42。",
            steps=2,
            evidence=RunEvidence(
                tool_executions=[
                    ToolExecutionRecord(
                        call_id="call_1",
                        name="add",
                        arguments={
                            "a": 12,
                            "b": 30,
                        },
                        status="success",
                    )
                ]
            ),
            run_id="smoke_run",
        )

async def main() -> None:
    configure_observability(
        ObservabilityConfig(
            exporter="console"
        )
    )
    observability = Observability()
    metrics = HarnessMetrics(
        observability
    )

    case = EvalCase(
        id="smoke",
        input="12 + 30 等于多少？",
        expected_answer_contains=("42",),
        expected_tools=("add",),
        forbidden_tools=("demo__multiply",),
        max_steps=3,
    )

    runner = EvaluationRunner(
        target=SmokeTarget(),
        evaluators=[
            AnswerContainsEvaluator(),
            RequiredToolEvaluator(),
            ForbiddenToolEvaluator(),
            MaxStepsEvaluator(),
        ],
        observability=observability,
        metrics=metrics,
    )

    result = await runner.run(
        suite_name="smoke",
        cases=[case],
    )

    assert_quality_gate(
        result,
        minimum_pass_rate=1.0,
        minimum_average_score=1.0,
    )

    print(
        "Evaluation Smoke Test（评估冒烟测试）通过。"
    )

if __name__ == "__main__":
    asyncio.run(main())