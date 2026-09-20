# 文件：harness/context/sources.py
from harness.context.models import Message

def select_recent_messages(
    messages: list[Message],
    limit: int,
) -> list[Message]:
    if limit <= 0:
        return []
    return messages[-limit:]
