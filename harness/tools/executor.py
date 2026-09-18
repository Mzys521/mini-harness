
import asyncio
import inspect

from harness.models import ToolCall
from harness.tools.definition import Tool, ToolContext
from harness.tools.errors import RetryableToolError
from harness.tools.registry import ToolRegistry
from harness.tools.result import ToolResult, ToolStatus
from harness.tools.validation import validate_tool_arguments
from time import perf_counter


class ToolExecutor:
    def __init__(self, registry: ToolRegistry , observability , metrics) -> None:
        self.registry = registry
        self.observability = observability
        self.metrics = metrics
        

    async def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:

        started = perf_counter()

        try:
            tool = self.registry.get(call.name)
        except ValueError as exc:
            return ToolResult(
                call_id=call.call_id, 
                tool_name=call.name, 
                status=ToolStatus.NOT_FOUND, 
                error_code="TOOL_NOT_FOUND", 
                error_message=str(exc)
            )
        
        attributes = {
            "tool.name": tool.name,
            "tool.source": tool.source,
        }
        self.metrics.tool_calls.add(1, attributes)

        with self.observability.span(
            "tool.execute",
            {
                **attributes,
                "agent.run_id": context.run_id,
            },
        ) as span:

            result = await self._execute_tool(
                tool=tool, 
                call=call, 
                context=context
            )

            span.set_attribute("tool.status", result.status.value)
            span.set_attribute("tool.attempts", result.attempts)

            metric_attributes = {
                **attributes,
                "status": result.status.value,
            }
            self.metrics.tool_duration.record(perf_counter() - started, metric_attributes)

            if not result.ok:
                self.metrics.tool_errors.add(1, metric_attributes)
                span.set_error(result.error_code or result.status.value)

            return result


    async def _execute_tool(self, tool: Tool, call: ToolCall, context: ToolContext) :
        try:
            validate_tool_arguments(tool.input_schema, call.arguments)
        except ValueError as exc:
            return ToolResult(
                call_id=call.call_id, 
                tool_name=tool.name, 
                status=ToolStatus.INVALID_ARGUMENTS, 
                error_code="INVALID_ARGUMENTS", 
                error_message=str(exc)
            )

        missing = tool.required_permissions - context.permissions
        if missing:
            return ToolResult(
                call_id=call.call_id, 
                tool_name=tool.name, 
                status=ToolStatus.PERMISSION_DENIED, 
                error_code="PERMISSION_DENIED", 
                error_message="missing permissions: " + ", ".join(sorted(missing))
            )

        max_attempts = tool.max_retries + 1
        for attempt in range(1, max_attempts + 1):
            try:
                data = await self._run_once(tool, call.arguments)
                return ToolResult(
                    call_id=call.call_id, 
                    tool_name=tool.name, 
                    status=ToolStatus.SUCCESS, 
                    data=data, 
                    attempts=attempt
                )
            except TimeoutError:
                return ToolResult(
                    call_id=call.call_id, 
                    tool_name=tool.name, 
                    status=ToolStatus.TIMEOUT, 
                    error_code="TOOL_TIMEOUT", 
                    error_message=f"tool exceeded {tool.timeout_seconds}s", 
                    attempts=attempt
                )
            except RetryableToolError as exc:
                if attempt >= max_attempts:
                    return ToolResult(
                        call_id=call.call_id, 
                        tool_name=tool.name, 
                        status=ToolStatus.ERROR, 
                        error_code="RETRY_EXHAUSTED", 
                        error_message=str(exc), 
                        attempts=attempt
                    )
                await asyncio.sleep(0.2 * attempt)
            except Exception as exc:
                return ToolResult(
                    call_id=call.call_id, 
                    tool_name=tool.name, 
                    status=ToolStatus.ERROR, 
                    error_code=type(exc).__name__, 
                    error_message=str(exc), 
                    attempts=attempt
                )

        raise AssertionError("unreachable")

    async def _run_once(self, tool: Tool, kwargs: dict):
        async with asyncio.timeout(tool.timeout_seconds):
            if inspect.iscoroutinefunction(tool.handler):
                return await tool.handler(**kwargs)
            return await asyncio.to_thread(tool.handler, **kwargs)


    
# 以下已在 0.6.0 版本中弃用 
# ----------------------------------------------------------------------------

# class ToolExecutor:
#     """工具执行器: 负责查找/校验/鉴权/中间件/超时/重试，统一返回 ToolResult"""

#     def __init__(self, registry: ToolRegistry, middlewares=None) -> None:
#         """初始化执行器。
#         参数 registry: 工具注册表(用于按名查找工具)
#         参数 middlewares: 中间件列表(before 正序执行，after 逆序执行)
#         """
#         self.registry = registry
#         self.middlewares = middlewares or []

#     # 执行工具
#     async def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
#         """执行一次工具调用(完整流程)。
#         流程: 查找工具 -> 参数校验 -> 权限检查 -> before 中间件 -> 带重试执行 -> after 中间件
#         参数 call: 模型给出的工具调用(名称/参数/call_id)
#         参数 context: 工具执行上下文(权限等)
#         返回: ToolResult 统一结果对象(失败以 status 表示，不向外抛异常)
#         """
#         try:
#             tool = self.registry.get(call.name)
#         except Exception as exc:
#             return ToolResult(
#                 call_id=call.call_id,
#                 tool_name=call.name,
#                 status=ToolStatus.NOT_FOUND,
#                 error_code="TOOL_NOT_FOUND",
#                 error_message=str(exc),
#             )

#         # 参数校验失败 -> INVALID_ARGUMENTS
#         try:
#             validated = tool.args_model.model_validate(call.arguments)
#         except ValidationError as exc:
#             return ToolResult(
#                 call_id=call.call_id,
#                 tool_name=tool.name,
#                 status=ToolStatus.INVALID_ARGUMENTS,
#                 error_code="INVALID_ARGUMENTS",
#                 error_message=str(exc),
#             )

#         # 权限检查: 缺少任一所需权限 -> PERMISSION_DENIED
#         missing = tool.required_permissions - context.permissions
#         if missing:
#             return ToolResult(
#                 call_id=call.call_id,
#                 tool_name=tool.name,
#                 status=ToolStatus.PERMISSION_DENIED,
#                 error_code="PERMISSION_DENIED",
#                 error_message="missing permissions: " + ", ".join(sorted(missing)),
#             )

#         # 执行前中间件(正序)
#         for middleware in self.middlewares:
#             await middleware.before_execute(tool, call, context)

#         result = await self._execute_with_retry(
#             tool=tool,
#             call=call,
#             kwargs=validated.model_dump(),
#         )

#         # 执行后中间件(逆序，与 before 对称)
#         for middleware in reversed(self.middlewares):
#             await middleware.after_execute(tool, call, context, result)

#         return result

#     # 执行工具并处理重试
#     async def _execute_with_retry(self, tool: Tool, call: ToolCall, kwargs: dict) -> ToolResult:
#         """按重试策略执行工具。
#         参数 tool: 工具定义(决定超时与重试次数)
#         参数 call: 原始调用(用于回填 call_id)
#         参数 kwargs: 已校验的工具参数字典
#         返回: ToolResult；Timeout/普通异常不重试，RetryableToolError 会重试
#         """
#         max_attempts = tool.max_retries + 1    # 总尝试次数 = 重试次数 + 1 次首次执行

#         for attempt in range(1, max_attempts + 1):
#             try:
#                 data = await self._run_once(tool, kwargs)
#                 return ToolResult(
#                     call_id=call.call_id,
#                     tool_name=tool.name,
#                     status=ToolStatus.SUCCESS,
#                     data=data,
#                     attempts=attempt,
#                 )

#             # 超时: 不重试，直接返回 TIMEOUT
#             except TimeoutError:
#                 return ToolResult(
#                     call_id=call.call_id,
#                     tool_name=tool.name,
#                     status=ToolStatus.TIMEOUT,
#                     error_code="TOOL_TIMEOUT",
#                     error_message=f"tool exceeded {tool.timeout_seconds}s",
#                     attempts=attempt,
#                 )

#             # 可重试错误: 次数用尽返回 RETRY_EXHAUSTED，否则退避后重试
#             except RetryableToolError as exc:
#                 if attempt >= max_attempts:
#                     return ToolResult(
#                         call_id=call.call_id,
#                         tool_name=tool.name,
#                         status=ToolStatus.ERROR,
#                         error_code="RETRY_EXHAUSTED",
#                         error_message=str(exc),
#                         attempts=attempt,
#                     )
#                 await asyncio.sleep(0.2 * attempt)    # 线性退避，避免紧密重试

#             # 其他异常: 直接返回 ERROR(不重试)
#             except Exception as exc:
#                 return ToolResult(
#                     call_id=call.call_id,
#                     tool_name=tool.name,
#                     status=ToolStatus.ERROR,
#                     error_code=type(exc).__name__,
#                     error_message=str(exc),
#                     attempts=attempt,
#                 )

#         raise AssertionError("unreachable")

#     # 运行工具一次
#     async def _run_once(self, tool: Tool, kwargs: dict):
#         """真正调用 handler 一次(带超时)。
#         参数 tool: 工具定义
#         参数 kwargs: 已校验的参数
#         返回: handler 结果；协程函数直接 await，同步函数放入线程池执行
#         """
#         async with asyncio.timeout(tool.timeout_seconds):
#             if inspect.iscoroutinefunction(tool.handler):
#                 return await tool.handler(**kwargs)
#             return await asyncio.to_thread(tool.handler, **kwargs)