import json

from harness.context.models import Message
from harness.context.models import ContextSection , WorkingState


# 选择最近的messages(滑动窗口)
def select_recent_messages(messages: list[Message] , limit: int , ) -> list[Message]:
    """取历史消息末尾的 limit 条(滑动窗口)。
    参数 messages: 完整历史消息列表
    参数 limit: 保留条数；<=0 时返回空列表
    返回: 最近的 limit 条消息
    """
    if limit <= 0 :
        return []
    return messages[-limit:]


# 工作状态section
def working_state_section(state: WorkingState , ) -> ContextSection:
    """把工作状态序列化为一个上下文片段。
    参数 state: 工作状态
    返回: ContextSection(名称 working_state，优先级 90)
    """
    content = json.dumps(
        {
            "goal": state.goal,
            "facts": state.facts,
            "completed_steps": state.completed_steps,
            "pending_steps": state.pending_steps,
        },
        ensure_ascii = False,
        indent = 2,
    )

    return ContextSection(
        name = "working_state",
        priority= 90,
        content = content,
    )


# 上下文投影
def trim_tool_results(text : str , max_chars: int) -> str:
    """截断过长的工具结果文本(上下文投影)。
    参数 text: 原始工具结果文本
    参数 max_chars: 允许的最大字符数
    返回: 未超限原样返回；超限则截断并附加省略数说明
    """
    if len(text) <= max_chars:
        return text
    
    omitted = len(text) - max_chars

    return (
        text[:max_chars]
        + "\n"
        + f"[TRUNCATED: {omitted} chars omitted]"
    )
