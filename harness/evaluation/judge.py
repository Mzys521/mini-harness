# 文件：harness/evaluation/judge.py
import json
import os
from typing import Any

from openai import AsyncOpenAI

from harness.evaluation.models import EvalCase, EvalSample, EvalScore

# 两个 Judge 共用同一套 Prompt 与评分契约，保证 DeepSeek 与 OpenAI 的判定口径一致。
_JUDGE_INSTRUCTIONS = (
    "你是严格的 AI 系统评估器。只依据给定用户输入、评分标准、参考答案和候选回答评分。"
    "不要因为回答更长就给更高分。score 必须位于 0 到 1。"
    "只输出 JSON 对象，字段为 score（number）与 reason（string）。"
)

# OpenAI Responses 接口使用的严格 JSON Schema（与 Prompt 中的契约同构）。
_SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "reason": {"type": "string"},
    },
    "required": ["score", "reason"],
    "additionalProperties": False,
}


def _judge_prompt(case: EvalCase, sample: EvalSample) -> str:
    reference = case.reference_answer or "未提供参考答案"
    rubric = case.rubric or "判断回答是否准确、相关并完成用户任务。"
    return (
        f"用户输入：\n{case.input}\n\n"
        f"评分标准：\n{rubric}\n\n"
        f"参考答案：\n{reference}\n\n"
        f"候选回答：\n{sample.output}"
    )


def _parse_score(payload: str) -> tuple[float, str]:
    """把 Judge 输出解析为 (score, reason)；格式异常时返回 0 分而不是抛异常。

    这里刻意不抛异常：单个 Case 的 Judge 输出畸形不应中断整轮评测
    （`EvaluationRunner.run` 没有 per-case 异常隔离）。
    """
    try:
        data: Any = json.loads(payload)
        score = float(data["score"])
        reason = str(data["reason"])
    except (ValueError, TypeError, KeyError) as exc:
        return 0.0, f"Judge 输出无法解析为评分 JSON：{exc}"
    return min(max(score, 0.0), 1.0), reason


class _JudgeEvaluator:
    """OpenAI / DeepSeek Judge 的共用骨架。

    两者同构：同一套 Prompt、同一评分契约、同一 EvalScore 结构，
    因此检索/评测链路可以在不改动 Evaluator 协议的前提下互换 Provider。
    """

    def __init__(self, *, model: str, pass_threshold: float = 0.8) -> None:
        self.model = model
        self.pass_threshold = pass_threshold

    @property
    def name(self) -> str:
        return "llm_judge"

    def applies_to(self, case: EvalCase) -> bool:
        return bool(case.rubric or case.reference_answer)

    def _score(self, payload: str, *, provider: str) -> EvalScore:
        score, reason = _parse_score(payload)
        return EvalScore(
            evaluator=self.name,
            score=score,
            passed=score >= self.pass_threshold,
            reason=reason,
            details={
                "judge_provider": provider,
                "judge_model": self.model,
                "pass_threshold": self.pass_threshold,
            },
        )


class OpenAIJudgeEvaluator(_JudgeEvaluator):
    """可选的 Reference-guided / Rubric-guided LLM Judge（OpenAI Responses 接口）。

    保留原有实现（Responses 接口 + 严格 JSON Schema 输出），只补齐 JSON 解析健壮性
    与显式凭据参数，使其与 DeepSeekJudgeEvaluator 完全同构。
    """

    def __init__(
        self,
        *,
        model: str,
        pass_threshold: float = 0.8,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model=model, pass_threshold=pass_threshold)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def evaluate(self, case: EvalCase, sample: EvalSample) -> EvalScore:
        response = await self.client.responses.create(
            model=self.model,
            instructions=_JUDGE_INSTRUCTIONS,
            input=_judge_prompt(case, sample),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "evaluation_score",
                    "strict": True,
                    "schema": _SCORE_SCHEMA,
                }
            },
        )
        return self._score(
            response.output_text,
            provider="openai",
        )


class DeepSeekJudgeEvaluator(_JudgeEvaluator):
    """与 OpenAIJudgeEvaluator 同构的 DeepSeek Judge（chat 接口 + JSON 输出）。

    参数默认从环境变量读取（`.env` 已提供 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` /
    `DEEPSEEK_BASE_URL`），因此可以零参构造：

        evaluator = DeepSeekJudgeEvaluator()

    DeepSeek 的 chat 接口不提供 Responses 的 `json_schema` 严格模式，
    因此这里用 `response_format={"type": "json_object"}` + 解析兜底达到同等契约。
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        pass_threshold: float = 0.8,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            model=(
                model
                or os.getenv("DEEPSEEK_MODEL")
                or "deepseek-chat"
            ),
            pass_threshold=pass_threshold,
        )
        self.client = AsyncOpenAI(
            api_key=(
                api_key
                or os.getenv("DEEPSEEK_API_KEY")
            ),
            base_url=(
                base_url
                or os.getenv("DEEPSEEK_BASE_URL")
            ),
        )

    async def evaluate(self, case: EvalCase, sample: EvalSample) -> EvalScore:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": _JUDGE_INSTRUCTIONS,
                },
                {
                    "role": "user",
                    "content": _judge_prompt(case, sample),
                },
            ],
            response_format={"type": "json_object"},
        )
        content = (
            response.choices[0].message.content
            or ""
        )
        return self._score(
            content,
            provider="deepseek",
        )
