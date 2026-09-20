# 文件：tests/test_security_evaluation.py
import pytest

from harness.evaluation.deterministic import (
    SecurityPolicyEvaluator,
)
from harness.evaluation.models import (
    EvalCase,
    EvalSample,
)
from harness.models import (
    RunEvidence,
    SecurityDecisionRecord,
)

@pytest.mark.asyncio
async def test_security_policy_evaluator_passes_expected_block() -> None:
    case = EvalCase(
        id="security_block",
        input="test",
        expected_security_codes=(
            "SEC_PROMPT_INJECTION_BLOCKED",
        ),
        expect_blocked=True,
    )

    sample = EvalSample(
        case_id=case.id,
        output="请求被安全策略阻止。",
        steps=0,
        evidence=RunEvidence(
            security_decisions=[
                SecurityDecisionRecord(
                    stage="input",
                    action="block",
                    code=(
                        "SEC_PROMPT_INJECTION_BLOCKED"
                    ),
                )
            ]
        ),
        run_id="run_security",
        blocked=True,
    )

    evaluator = (
        SecurityPolicyEvaluator()
    )
    score = await evaluator.evaluate(
        case,
        sample,
    )

    assert score.passed
    assert score.score == 1.0

@pytest.mark.asyncio
async def test_security_policy_evaluator_detects_missing_control() -> None:
    case = EvalCase(
        id="security_missing",
        input="test",
        expected_security_codes=(
            "SEC_APPROVAL_REQUIRED",
        ),
    )

    sample = EvalSample(
        case_id=case.id,
        output="",
        steps=1,
        evidence=RunEvidence(),
        run_id="run_missing",
        blocked=False,
    )

    evaluator = (
        SecurityPolicyEvaluator()
    )
    score = await evaluator.evaluate(
        case,
        sample,
    )

    assert score.passed is False
    assert (
        "SEC_APPROVAL_REQUIRED"
        in score.details[
            "missing_codes"
        ]
    )