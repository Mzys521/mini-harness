# 文件：harness/tools/middleware.py
from typing import Protocol

from harness.models import ToolCall
from harness.tools.definition import Tool, ToolContext
from harness.tools.result import ToolResult

class ToolMiddleware(Protocol):
    """Phase 2 恢复：Tool Runtime 的横切扩展点。"""

    async def before_execute(
        self,
        tool: Tool,
        call: ToolCall,
        context: ToolContext,
    ) -> None:
        ...

    async def after_execute(
        self,
        tool: Tool,
        call: ToolCall,
        context: ToolContext,
        result: ToolResult,
    ) -> None:
        ...
