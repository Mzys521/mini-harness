import json
from dataclasses import asdict
from pathlib import Path

from harness.evaluation.models import (
    EvalRunResult,
)

class EvaluationGateError(RuntimeError):
    """Evaluation Quality Gate（评估质量门）未通过。"""

def write_json_report(result: EvalRunResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            asdict(result),
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return output_path

def assert_quality_gate(result: EvalRunResult,*, minimum_pass_rate: float,minimum_average_score: float,) -> None:
    problems: list[str] = []

    if (
        result.summary.pass_rate
        < minimum_pass_rate
    ):
        problems.append(
            "pass_rate "
            f"{result.summary.pass_rate:.3f} "
            f"< {minimum_pass_rate:.3f}"
        )

    if (
        result.summary.average_score
        < minimum_average_score
    ):
        problems.append(
            "average_score "
            f"{result.summary.average_score:.3f} "
            f"< {minimum_average_score:.3f}"
        )

    if problems:
        raise EvaluationGateError(
            "; ".join(problems)
        )