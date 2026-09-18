from dataclasses import dataclass

@dataclass(frozen=True)
class TokenBudget:
    max_context_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int = 512

    @property
    def available_input_tokens(self) -> int:
        return max(
            0,
            self.max_context_tokens
            - self.reserved_output_tokens
            - self.safety_margin_tokens,
        )

class ApproxTokenCounter:
    """教学估算器；生产版应替换为 Model-aware Tokenizer（模型感知分词器）。"""
    def count_text(self, text: str) -> int:
        return 0 if not text else max(1, len(text) // 3)