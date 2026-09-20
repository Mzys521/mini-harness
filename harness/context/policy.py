# 文件：harness/context/policy.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ContextPolicy:
    """Context Selection（上下文选择）策略，与 Builder 机制分离。"""

    recent_message_limit: int = 20
    include_working_state: bool = True
    include_retrieved_context: bool = True
    include_external_context: bool = True
