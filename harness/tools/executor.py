import asyncio
import inspect
from time import perf_counter

from harness.models import ToolCall
from harness.tools.definition import (
    Tool,
    ToolContext,
)
from harness.tools.registry import ToolRegistry
from harness.tools.result import (
    ToolResult,
    ToolStatus,
)
from harness.tools.validation import (
    validate_tool_arguments,
)

class RetryableToolError(Exception):
    """只有明确可安全重试的临时错误才使用。"""

class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        observability,
        metrics,
    ) -> None:
        self.registry = registry
        self.observability = observability
        self.metrics = metrics

    async def execute(
        self,
        call: ToolCall,
        context: ToolContext,
    ) -> ToolResult:
        started = perf_counter()

        try:
            tool = self.registry.get(
                call.name
            )
        except ValueError as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.name,
                status=ToolStatus.NOT_FOUND,
                error_code="TOOL_NOT_FOUND",
                error_message=str(exc),
            )

        attributes = {
            "tool.name": tool.name,
            "tool.source": tool.source,
        }

        self.metrics.tool_calls.add(
            1,
            attributes,
        )

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
                context=context,
            )

            span.set_attribute(
                "tool.status",
                result.status.value,
            )
            span.set_attribute(
                "tool.attempts",
                result.attempts,
            )

            metric_attributes = {
                **attributes,
                "status": result.status.value,
            }

            self.metrics.tool_duration.record(
                perf_counter() - started,
                metric_attributes,
            )

            if not result.ok:
                self.metrics.tool_errors.add(
                    1,
                    metric_attributes,
                )
                span.set_error(
                    result.error_code
                    or result.status.value
                )

            return result

    async def _execute_tool(
        self,
        *,
        tool: Tool,
        call: ToolCall,
        context: ToolContext,
    ) -> ToolResult:
        try:
            validate_tool_arguments(
                tool.input_schema,
                call.arguments,
            )
        except ValueError as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=tool.name,
                status=ToolStatus.INVALID_ARGUMENTS,
                error_code="INVALID_ARGUMENTS",
                error_message=str(exc),
            )

        missing = (
            tool.required_permissions
            - context.permissions
        )

        if missing:
            return ToolResult(
                call_id=call.call_id,
                tool_name=tool.name,
                status=ToolStatus.PERMISSION_DENIED,
                error_code="PERMISSION_DENIED",
                error_message=(
                    "missing permissions: "
                    + ", ".join(sorted(missing))
                ),
            )

        max_attempts = (
            tool.max_retries + 1
        )

        for attempt in range(
            1,
            max_attempts + 1,
        ):
            try:
                data = await self._run_once(
                    tool=tool,
                    kwargs=call.arguments,
                    context=context,
                )

                return ToolResult(
                    call_id=call.call_id,
                    tool_name=tool.name,
                    status=ToolStatus.SUCCESS,
                    data=data,
                    attempts=attempt,
                )

            except TimeoutError:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=tool.name,
                    status=ToolStatus.TIMEOUT,
                    error_code="TOOL_TIMEOUT",
                    error_message=(
                        "tool exceeded "
                        f"{tool.timeout_seconds}s"
                    ),
                    attempts=attempt,
                )

            except RetryableToolError as exc:
                if attempt >= max_attempts:
                    return ToolResult(
                        call_id=call.call_id,
                        tool_name=tool.name,
                        status=ToolStatus.ERROR,
                        error_code="RETRY_EXHAUSTED",
                        error_message=str(exc),
                        attempts=attempt,
                    )

                await asyncio.sleep(
                    0.2 * attempt
                )

            except Exception as exc:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=tool.name,
                    status=ToolStatus.ERROR,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                    attempts=attempt,
                )

        raise AssertionError("unreachable")

    async def _run_once(
        self,
        *,
        tool: Tool,
        kwargs: dict,
        context: ToolContext,
    ):
        # ToolContext 是 Harness 可信数据，不出现在 LLM Tool Schema 中。
        handler_kwargs = dict(kwargs)

        if tool.inject_context:
            handler_kwargs["context"] = (
                context
            )

        async with asyncio.timeout(
            tool.timeout_seconds
        ):
            if inspect.iscoroutinefunction(
                tool.handler
            ):
                return await tool.handler(
                    **handler_kwargs
                )

            return await asyncio.to_thread(
                tool.handler,
                **handler_kwargs,
            )