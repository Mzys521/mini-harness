# 文件：harness/context/budget.py
from dataclasses import dataclass
from typing import Protocol

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

class TokenCounter(Protocol):
    def count_text(self, text: str) -> int:
        ...

class ApproxTokenCounter:
    """教学估算器；生产环境应替换成模型感知 Tokenizer。"""

    def count_text(self, text: str) -> int:
        if not text:
            return 0
        return max(
            1,
            len(text) // 3,
        )
