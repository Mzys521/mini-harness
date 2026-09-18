from time import perf_counter

from harness.evaluation.models import (
    EvalCaseResult,
    EvalRunResult,
    EvalSummary,
    utc_now,
)

class EvaluationRunner:
    """评估运行器"""
    def __init__(self, target, evaluators, observability, metrics):
        """初始化评估运行器

        :param target: 评估目标
        :param evaluators: 评估器
        :param observability: 可观察性
        :param metrics: 指标
        """
        self.target = target
        self.evaluators = list(evaluators)
        self.observability = observability
        self.metrics = metrics

    async def run(self, * , suite_name: str, cases):
        """运行评估

        :param suite_name: 评估套件名称
        :param cases: 评估用例
        :return: 评估结果
        """
        started_at = utc_now()
        results: list[EvalCaseResult] = []

        with self.observability.span(
            "evaluation.run",
            {
                "evaluation.suite": suite_name,
                "evaluation.case_count": len(cases),
            },
        ) as run_span:
            for case in cases:
                started = perf_counter()

                with self.observability.span(
                    "evaluation.case",
                    {
                        "evaluation.suite": suite_name,
                        "evaluation.case_id": case.id,
                    },
                ) as case_span:
                    sample = await self.target.run_case(case)

                    scores = []

                    for evaluator in self.evaluators:
                        if not evaluator.applies_to(case):
                            continue

                        score = await evaluator.evaluate(case,sample,)
                        scores.append(score)

                    case_result = EvalCaseResult(
                        case=case,
                        sample=sample,
                        scores=tuple(scores),
                    )
                    results.append(case_result)

                    case_span.set_attribute(
                        "evaluation.passed",
                        case_result.passed,
                    )
                    case_span.set_attribute(
                        "evaluation.score",
                        case_result.average_score,
                    )

                    self.metrics.eval_cases.add(
                        1,
                        {
                            "suite": suite_name,
                            "status": (
                                "passed"
                                if case_result.passed
                                else "failed"
                            ),
                        },
                    )
                    self.metrics.eval_case_duration.record(
                        perf_counter() - started,
                        {"suite": suite_name},
                    )

        total = len(results)
        passed = sum(1 for item in results if item.passed)
        average_score = (sum(item.average_score for item in results) / total if total else 0.0)


        summary = EvalSummary(
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            pass_rate=(passed / total if total else 0.0),
            average_score=average_score,
        )

        run_span.set_attribute(
            "evaluation.pass_rate",
            summary.pass_rate,
        )
        run_span.set_attribute(
            "evaluation.average_score",
            summary.average_score,
        )

        return EvalRunResult(
            suite_name=suite_name,
            started_at=started_at,
            completed_at=utc_now(),
            results=tuple(results),
            summary=summary,
        )