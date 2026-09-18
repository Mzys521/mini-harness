import argparse
import json
from pathlib import Path

def load_summary(path: str) -> dict:
    data = json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )
    return data["summary"]

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "比较当前 Evaluation Report "
            "和 Baseline Report"
        )
    )
    parser.add_argument(
        "baseline",
    )
    parser.add_argument(
        "current",
    )
    parser.add_argument(
        "--max-pass-rate-drop",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--max-score-drop",
        type=float,
        default=0.02,
    )
    args = parser.parse_args()

    baseline = load_summary(
        args.baseline
    )
    current = load_summary(
        args.current
    )

    pass_rate_drop = (
        baseline["pass_rate"]
        - current["pass_rate"]
    )
    score_drop = (
        baseline["average_score"]
        - current["average_score"]
    )

    print(
        "Baseline Pass Rate："
        f"{baseline['pass_rate']:.2%}"
    )
    print(
        "Current Pass Rate："
        f"{current['pass_rate']:.2%}"
    )
    print(
        "Baseline Average Score："
        f"{baseline['average_score']:.3f}"
    )
    print(
        "Current Average Score："
        f"{current['average_score']:.3f}"
    )

    problems = []

    if (
        pass_rate_drop
        > args.max_pass_rate_drop
    ):
        problems.append(
            "pass rate regression: "
            f"{pass_rate_drop:.3f}"
        )

    if (
        score_drop
        > args.max_score_drop
    ):
        problems.append(
            "average score regression: "
            f"{score_drop:.3f}"
        )

    if problems:
        raise SystemExit(
            "Evaluation regression detected: "
            + "; ".join(problems)
        )

    print(
        "Regression Gate（回归质量门）通过。"
    )

if __name__ == "__main__":
    main()