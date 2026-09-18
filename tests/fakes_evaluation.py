from harness.evaluation.models import (
    EvalCase,
    EvalSample,
)
from harness.models import (
    RunEvidence,
    ToolExecutionRecord,
)

class FakeEvaluationTarget:
    """通过 Case ID 返回预设结果，让 Evaluator 单元测试完全确定。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run_case(
        self,
        case: EvalCase,
    ) -> EvalSample:
        self.calls.append(case.id)

        if case.id == "good":
            return EvalSample(
                case_id=case.id,
                output="结果是 42。",
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
                run_id="run_good",
            )

        return EvalSample(
            case_id=case.id,
            output="不知道。",
            steps=6,
            evidence=RunEvidence(),
            run_id="run_bad",
        )