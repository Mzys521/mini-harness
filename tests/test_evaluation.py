import json

import pytest

from harness.evaluation import (
    AnswerContainsEvaluator,
    EvaluationGateError,
    EvaluationRunner,
    ForbiddenToolEvaluator,
    MaxStepsEvaluator,
    RequiredToolEvaluator,
    assert_quality_gate,
    load_jsonl_dataset,
)
from harness.evaluation.models import (
    EvalCase,
)
from tests.fakes_evaluation import (
    FakeEvaluationTarget,
)
from tests.fakes_observability import (
    FakeMetrics,
    FakeObservability,
)

@pytest.mark.asyncio
async def test_good_case_passes_all_evaluators() -> None:
    case = EvalCase(
        id="good",
        input="12 + 30 等于多少？",
        expected_answer_contains=("42",),
        expected_tools=("add",),
        forbidden_tools=("demo__multiply",),
        max_steps=3,
    )

    runner = EvaluationRunner(
        target=FakeEvaluationTarget(),
        evaluators=[
            AnswerContainsEvaluator(),
            RequiredToolEvaluator(),
            ForbiddenToolEvaluator(),
            MaxStepsEvaluator(),
        ],
        observability=FakeObservability(),
        metrics=FakeMetrics(),
    )

    result = await runner.run(
        suite_name="unit",
        cases=[case],
    )

    assert result.summary.total_cases == 1
    assert result.summary.passed_cases == 1
    assert result.summary.pass_rate == 1.0
    assert result.results[0].passed is True

@pytest.mark.asyncio
async def test_bad_case_fails_quality_gate() -> None:
    case = EvalCase(
        id="bad",
        input="12 + 30 等于多少？",
        expected_answer_contains=("42",),
        expected_tools=("add",),
        max_steps=3,
    )

    runner = EvaluationRunner(
        target=FakeEvaluationTarget(),
        evaluators=[
            AnswerContainsEvaluator(),
            RequiredToolEvaluator(),
            MaxStepsEvaluator(),
        ],
        observability=FakeObservability(),
        metrics=FakeMetrics(),
    )

    result = await runner.run(
        suite_name="unit",
        cases=[case],
    )

    assert result.summary.failed_cases == 1

    with pytest.raises(
        EvaluationGateError
    ):
        assert_quality_gate(
            result,
            minimum_pass_rate=1.0,
            minimum_average_score=1.0,
        )

def test_jsonl_dataset_loader(tmp_path) -> None:
    dataset = tmp_path / "eval.jsonl"
    rows = [
        {
            "id": "case_1",
            "input": "hello",
            "expected_answer_contains": [
                "hello"
            ],
        },
        {
            "id": "case_2",
            "input": "2+3",
            "expected_tools": ["add"],
        },
    ]

    dataset.write_text(
        "\n".join(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            for row in rows
        ),
        encoding="utf-8",
    )

    cases = load_jsonl_dataset(
        dataset
    )

    assert len(cases) == 2
    assert cases[1].expected_tools == (
        "add",
    )