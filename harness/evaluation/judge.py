import json

from openai import AsyncOpenAI

from harness.evaluation.models import EvalCase, EvalSample, EvalScore


class OpenAIJudgeEvaluator:
    """可选的 Reference-guided / Rubric-guided LLM Judge（参考答案/评分标准裁判）。"""

    def __init__(self, *, model: str, pass_threshold: float = 0.8) -> None:
        self.client = AsyncOpenAI()
        self.model = model
        self.pass_threshold = pass_threshold

    @property
    def name(self) -> str:
        return "llm_judge"

    def applies_to(self, case: EvalCase) -> bool:
        return bool(case.rubric or case.reference_answer)

    async def evaluate(self, case: EvalCase, sample: EvalSample) -> EvalScore:
        reference = case.reference_answer or "未提供参考答案"
        rubric = case.rubric or "判断回答是否准确、相关并完成用户任务。"

        response = await self.client.responses.create(
            model=self.model, 
            instructions="你是严格的 AI 系统评估器。只依据给定用户输入、评分标准、参考答案和候选回答评分。不要因为回答更长就给更高分。score 必须位于 0 到 1。", 
            input=f"用户输入：\n{case.input}\n\n评分标准：\n{rubric}\n\n参考答案：\n{reference}\n\n候选回答：\n{sample.output}", 
            text={
                "format": {"type": "json_schema", "name": "evaluation_score", 
                "strict": True, 
                "schema": {
                    "type": "object", 
                    "properties": {
                        "score": {
                            "type": "number", "minimum": 0, "maximum": 1}, 
                        "reason": {"type": "string"}
                        }, 
                        "required": ["score", "reason"], 
                        "additionalProperties": False,
                        }
                    }
                }
            )

        data = json.loads(response.output_text)
        score = float(data["score"])

        return EvalScore(
            evaluator=self.name,
            score=score,
            passed=score >= self.pass_threshold,
            reason=data["reason"],
            details={"judge_model": self.model, "pass_threshold": self.pass_threshold},
        )
