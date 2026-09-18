from openai.types.responses.response_code_interpreter_tool_call import Output

from harness.evaluation.models import EvalCase, EvalSample, EvalScore

class AnswerContainsEvaluator:
    """答案包含评估器"""
    @property
    def name(self) ->str:
        return "answer_contains"

    def applies_to(self , case: EvalCase) -> bool:
        return bool(case.expected_answer_contains)

    async def evaluate(self , case : EvalCase , sample : EvalSample ,) -> EvalScore:
        output = sample.output.casefold()

        missing = [item for item in case.expected_answer_contains if item not in output]
        total = len(case.expected_answer_contains)

        matched = total - len(missing)

        score =(matched / total if total else 1.0)

        return EvalScore(
            evaluator = self.name,
            score=score,
            passed = not missing,
            reason = ("所有必需内容均出现"if not missing else f"缺少内容：{missing}") ,
            details = {"missing" : missing},
        )

class RequiredToolEvaluator:
    """所需工具评估器"""
    @property
    def name(self) ->str:
        return "required_tool"

    def applies_to(self , case: EvalCase) -> bool:
        return bool(case.expected_tools)

    async def evaluate(self , case : EvalCase , sample : EvalSample ,) -> EvalScore:
        actual = {item.name for item in sample.evidence.tool_executions}
        expected = set(case.expected_tools)

        missing = sorted(expected - actual)

        score = (len(expected & actual) / len(expected) if expected else 1.0)

        return EvalScore(
            evaluator=self.name,
            score=score,
            passed=not missing,
            reason=("所有必需 Tool 均被调用" if not missing else f"未调用必需 Tool：{missing}"),
            details={
                "expected": sorted(expected),
                "actual": sorted(actual),
                "missing": missing,
            },
        )

class ForbiddenToolEvaluator:
    """禁止工具评估器"""

    @property
    def name(self) ->str:
        return "forbidden_tools"
    
    def applies_to(self , case: EvalCase) -> bool:
        return bool(case.forbidden_tools)

    async def evaluate(self , case : EvalCase , sample : EvalSample ,) -> EvalScore:
        actual = {item.name for item in sample.evidence.tool_executions}
        forbidden_used = set(sorted(actual & set(case.forbidden_tools)))

        missing = sorted(forbidden_used - actual)

        score = (len(forbidden_used & actual) / len(forbidden_used) if forbidden_used else 1.0)

        return EvalScore(
            evaluator=self.name,
            score=score,
            passed=not missing,
            reason=("未使用禁止 Tool" if not missing else f"调用了禁止 Tool：{forbidden_used}"),
            details={
                "forbidden_used": forbidden_used,
            },
        )

class MaxStepsEvaluator:
    """最大步骤评估器"""
    @property
    def name(self) -> str:
        return "max_steps"

    def applies_to(self, case: EvalCase) -> bool:
        return case.max_steps is not None

    async def evaluate(self,case: EvalCase,sample: EvalSample,) -> EvalScore:
        assert case.max_steps is not None
        passed = sample.steps <= case.max_steps

        return EvalScore(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
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





