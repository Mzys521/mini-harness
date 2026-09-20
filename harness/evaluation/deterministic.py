# 文件：harness/evaluation/deterministic.py
from harness.evaluation.models import (
    EvalCase,
    EvalSample,
    EvalScore,
)

class AnswerContainsEvaluator:
    @property
    def name(self) -> str:
        return "answer_contains"

    def applies_to(
        self,
        case: EvalCase,
    ) -> bool:
        return bool(
            case.expected_answer_contains
        )

    async def evaluate(
        self,
        case: EvalCase,
        sample: EvalSample,
    ) -> EvalScore:
        output = (
            sample.output.casefold()
        )
        missing = [
            item
            for item in case.expected_answer_contains
            if item.casefold()
            not in output
        ]

        total = len(
            case.expected_answer_contains
        )
        matched = (
            total - len(missing)
        )
        score = (
            matched / total
            if total
            else 1.0
        )

        return EvalScore(
            evaluator=self.name,
            score=score,
            passed=not missing,
            reason=(
                "所有必需内容均出现"
                if not missing
                else f"缺少内容：{missing}"
            ),
            details={
                "missing": missing
            },
        )

class RequiredToolEvaluator:
    @property
    def name(self) -> str:
        return "required_tools"

    def applies_to(
        self,
        case: EvalCase,
    ) -> bool:
        return bool(
            case.expected_tools
        )

    async def evaluate(
        self,
        case: EvalCase,
        sample: EvalSample,
    ) -> EvalScore:
        actual = {
            item.name
            for item
            in sample.evidence.tool_executions
        }
        expected = set(
            case.expected_tools
        )
        missing = sorted(
            expected - actual
        )

        score = (
            len(expected & actual)
            / len(expected)
            if expected
            else 1.0
        )

        return EvalScore(
            evaluator=self.name,
            score=score,
            passed=not missing,
            reason=(
                "所有必需 Tool 均被调用"
                if not missing
                else f"未调用必需 Tool：{missing}"
            ),
            details={
                "expected": sorted(expected),
                "actual": sorted(actual),
                "missing": missing,
            },
        )

class ForbiddenToolEvaluator:
    @property
    def name(self) -> str:
        return "forbidden_tools"

    def applies_to(
        self,
        case: EvalCase,
    ) -> bool:
        return bool(
            case.forbidden_tools
        )

    async def evaluate(
        self,
        case: EvalCase,
        sample: EvalSample,
    ) -> EvalScore:
        actual = {
            item.name
            for item
            in sample.evidence.tool_executions
        }
        forbidden_used = sorted(
            actual
            & set(
                case.forbidden_tools
            )
        )

        return EvalScore(
            evaluator=self.name,
            score=(
                0.0
                if forbidden_used
                else 1.0
            ),
            passed=not forbidden_used,
            reason=(
                "未使用禁止 Tool"
                if not forbidden_used
                else f"调用了禁止 Tool：{forbidden_used}"
            ),
            details={
                "forbidden_used": (
                    forbidden_used
                )
            },
        )

class MaxStepsEvaluator:
    @property
    def name(self) -> str:
        return "max_steps"

    def applies_to(
        self,
        case: EvalCase,
    ) -> bool:
        return (
            case.max_steps
            is not None
        )

    async def evaluate(
        self,
        case: EvalCase,
        sample: EvalSample,
    ) -> EvalScore:
        assert (
            case.max_steps
            is not None
        )

        passed = (
            sample.steps
            <= case.max_steps
        )

        return EvalScore(
            evaluator=self.name,
            score=(
                1.0
                if passed
                else 0.0
            ),
            passed=passed,
            reason=(
                f"steps={sample.steps}, "
                f"limit={case.max_steps}"
            ),
            details={
                "steps": sample.steps,
                "max_steps": case.max_steps,
            },
        )

class SecurityPolicyEvaluator:
    """验证 Security Decision 是否符合 Dataset 的明确期望。"""

    @property
    def name(self) -> str:
        return "security_policy"

    def applies_to(
        self,
        case: EvalCase,
    ) -> bool:
        return bool(
            case.expected_security_codes
        ) or (
            case.expect_blocked
            is not None
        )

    async def evaluate(
        self,
        case: EvalCase,
        sample: EvalSample,
    ) -> EvalScore:
        actual_codes = {
            item.code
            for item
            in sample.evidence.security_decisions
        }
        expected_codes = set(
            case.expected_security_codes
        )

        missing_codes = sorted(
            expected_codes
            - actual_codes
        )

        checks: list[bool] = []

        if expected_codes:
            checks.append(
                not missing_codes
            )

        if (
            case.expect_blocked
            is not None
        ):
            checks.append(
                sample.blocked
                == case.expect_blocked
            )

        passed = all(
            checks
        ) if checks else True

        score = (
            sum(
                1
                for item in checks
                if item
            )
            / len(checks)
            if checks
            else 1.0
        )

        return EvalScore(
            evaluator=self.name,
            score=score,
            passed=passed,
            reason=(
                "Security Policy 符合预期"
                if passed
                else "Security Policy 与预期不一致"
            ),
            details={
                "expected_codes": sorted(
                    expected_codes
                ),
                "actual_codes": sorted(
                    actual_codes
                ),
                "missing_codes": missing_codes,
                "expected_blocked": (
                    case.expect_blocked
                ),
                "actual_blocked": (
                    sample.blocked
                ),
            },
        )