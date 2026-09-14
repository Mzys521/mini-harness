import time

from typing import Protocol
from harness.models import ToolCall
from harness.tools.definition import Tool, ToolContext
from harness.tools.result import ToolResult


class ToolMiddleware(Protocol):
    """工具中间件协议: 实现下面两个钩子即视为一个中间件"""

    async def before_execute(self, tool:Tool , call:ToolCall , context:ToolContext)->None:
        """在工具执行之前执行的中间件。
        参数 tool: 工具定义 / call: 本次调用 / context: 执行上下文
        """
    
    async def after_execute(self, tool:Tool , call:ToolCall , context:ToolContext , result:ToolResult)->None:
        """在工具执行之后执行的中间件。
        参数 tool: 工具定义 / call: 本次调用 / context: 执行上下文 / result: 执行结果
        """


class LoggingMiddleware:
    """日志中间件: 记录每次工具调用的开始与结束(含耗时)"""

    def __init__(self) -> None:
        """初始化，用 call_id 记录各次调用的开始时间"""
        self._started_at : dict[str , float] = {}

    async def before_execute(self, tool:Tool , call:ToolCall , context:ToolContext)->None:
        """记录开始时间并打印 [tool.start] 日志。
        参数 tool: 工具定义 / call: 本次调用 / context: 执行上下文
        """
        self._started_at[call.call_id] = time.perf_counter()
        print(
            f"[tool.start] run={context.run_id}"
            f" tool={tool.name} call={call.call_id}"
        )

    async def after_execute(self, tool:Tool , call:ToolCall , context:ToolContext , result:ToolResult)->None:
        """弹出开始时间，计算耗时并打印 [tool.finish] 日志。
        参数 tool: 工具定义 / call: 本次调用 / context: 执行上下文 / result: 执行结果
        """
        started = self._started_at.pop(call.call_id , time.perf_counter())
        duration_ms = (time.perf_counter() - started) * 1000
        print(
            f"[tool.finish] run={context.run_id}"
            f" tool={tool.name} status={result.status} "
            f" duration_ms={duration_ms:.2f}"
        )
