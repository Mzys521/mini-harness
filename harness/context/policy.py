from dataclasses import dataclass

@dataclass(frozen=True)
class ContextPolicy:
    """上下文构建策略(不可变)"""
    recent_messages_limit : int = 12    # 历史消息滑动窗口条数
    include_working_state : bool = True    # 是否注入工作状态
    include_tool_results : bool = True    # 是否包含工具结果(预留开关)
    max_tool_result_chars : int = 6000    # 单条工具结果最大字符数(超出截断)



