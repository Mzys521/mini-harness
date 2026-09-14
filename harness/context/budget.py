from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class TokenBudget:
    """Token 预算配置(不可变)"""
    max_context_tokens: int    # 模型上下文窗口上限
    reserved_output_tokens: int    # 为输出预留的 token
    safety_margin_tokens: int = 512    # 安全余量

    # 计算可用的输入token数
    @property
    def available_input_tokens(self) -> int:
        """可用于输入的最大 token 数 = 窗口上限 - 输出预留 - 安全余量(不小于 0)"""
        value = (
            self.max_context_tokens
            - self.reserved_output_tokens
            - self.safety_margin_tokens     # 安全余量 , 防止输入过大导致输出截断
        )
        return max(0 , value)

class TokenCounter(Protocol):
    """Token 计数器协议: 实现 count_text 方法即可作为计数器使用"""
    def count_text(self , text : str) ->int:
        """统计文本的 token 数。参数 text: 待统计文本"""
        ...

# 估算token数
class ApproxTokenCounter:
    """粗略的 token 估算器: 约 3 个字符 ≈ 1 token"""
    def count_text(self,text:str) -> int:
        """估算文本的 token 数。
        参数 text: 待统计文本；空文本返回 0
        返回: 至少为 1 的估算值(len(text) // 3)
        """
        if not text:
            return 0
        return max(1 , len(text) // 3)
