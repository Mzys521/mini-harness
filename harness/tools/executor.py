# 文件：harness/tools/executor.py
import asyncio
import hashlib
import inspect
import json
from time import perf_counter

from harness.models import ToolCall
from harness.security.models import SecurityAction
from harness.tools.definition import Tool, ToolContext
from harness.tools.idempotency import IdempotencyStatus
from harness.tools.registry import ToolRegistry
from harness.tools.result import ToolResult, ToolStatus
from harness.tools.validation import validate_tool_arguments

class RetryableToolError(Exception):
    """只有明确可安全重试的临时错误才使用。"""

class ToolExecutor:
    """统一执行 Local / RAG / MCP Tool。

    执行顺序：
    Registry → Schema Validation → Permission → Security Policy
    → Middleware(before) → Idempotency → Timeout/Retry/Handler
    → Middleware(after) → Tool Result Security Projection。
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        observability=None,
        metrics=None,
        security=None,
        middlewares=None,
        idempotency_store=None,
    ) -> None:
        self.registry = registry
        self.observability = (
            observability
            or _NoopObservability()
        )
        self.metrics = (
            metrics
            or _NoopMetrics()
        )
        self.security = security
        self.middlewares = list(
            middlewares or []
        )
        self.idempotency_store = (
            idempotency_store
        )

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

            # External Tool Result 回流下一轮模型前做安全投影。
            if (
                self.security is not None
                and result.ok
            ):
                (
                    safe_model_output,
                    result_decisions,
                ) = self.security.inspect_tool_result(
                    text=result.to_model_output(),
                    run_id=context.run_id,
                    tool_name=tool.name,
                )
                result.model_output_override = (
                    safe_model_output
                )
                result.security_codes.extend(
                    decision.code
                    for decision in result_decisions
                    if decision.code
                    not in {
                        "SEC_OUTPUT_SECRET_CLEAR",
                        "SEC_OUTPUT_LENGTH_OK",
                    }
                )

            span.set_attribute(
                "tool.status",
                result.status.value,
            )
            span.set_attribute(
                "tool.attempts",
                result.attempts,
            )
            if result.security_code:
                span.set_attribute(
                    "security.code",
                    result.security_code,
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
        # 1. Schema Validation。
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

        # 2. Business Permission。
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

        # 3. Deterministic Security Policy / Approval。
        if self.security is not None:
            decision = (
                self.security.authorize_tool(
                    tool=tool,
                    call=call,
                    context=context,
                )
            )

            if (
                decision.action
                == SecurityAction.APPROVAL_REQUIRED
            ):
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=tool.name,
                    status=ToolStatus.APPROVAL_REQUIRED,
                    error_code="APPROVAL_REQUIRED",
                    error_message=decision.reason,
                    security_code=decision.code,
                    security_codes=[
                        decision.code
                    ],
                )

            if not decision.allowed:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=tool.name,
                    status=ToolStatus.SECURITY_DENIED,
                    error_code="SECURITY_DENIED",
                    error_message=decision.reason,
                    security_code=decision.code,
                    security_codes=[
                        decision.code
                    ],
                )

        # 4. Phase 2 Middleware 恢复。
        for middleware in self.middlewares:
            await middleware.before_execute(
                tool,
                call,
                context,
            )

        try:
            result = (
                await self._execute_with_idempotency(
                    tool=tool,
                    call=call,
                    context=context,
                )
            )
        finally:
            # after_execute 需要 Result；异常只应来自 Runtime Bug，
            # 正常 Tool Error 已统一转换为 ToolResult。
            pass

        for middleware in reversed(
            self.middlewares
        ):
            await middleware.after_execute(
                tool,
                call,
                context,
                result,
            )

        return result

    async def _execute_with_idempotency(
        self,
        *,
        tool: Tool,
        call: ToolCall,
        context: ToolContext,
    ) -> ToolResult:
        idempotency_key = (
            f"{context.run_id}:"
            f"{call.call_id}:"
            f"{tool.name}"
        )
        payload_hash = hashlib.sha256(
            json.dumps(
                call.arguments,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        if (
            tool.side_effect
            and self.idempotency_store
            is not None
        ):
            record = (
                self.idempotency_store.begin(
                    idempotency_key=idempotency_key,
                    run_id=context.run_id,
                    call_id=call.call_id,
                    tool_name=tool.name,
                    payload_hash=payload_hash,
                )
            )

            if (
                record.payload_hash
                != payload_hash
            ):
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=tool.name,
                    status=ToolStatus.SECURITY_DENIED,
                    error_code="IDEMPOTENCY_PAYLOAD_CONFLICT",
                    error_message=(
                        "同一个 idempotency key 对应了不同参数。"
                    ),
                )

            if (
                record.status
                == IdempotencyStatus.COMPLETED
                and record.result is not None
            ):
                return record.result

            if (
                record.status
                == IdempotencyStatus.UNCERTAIN
            ):
                return self._reconciliation_required(
                    tool=tool,
                    call=call,
                    message=(
                        record.error_message
                        or "之前的副作用执行结果未知，需要人工核对。"
                    ),
                )

            if (
                not record.acquired
                and record.status
                == IdempotencyStatus.STARTED
                and not tool.idempotent
            ):
                return self._reconciliation_required(
                    tool=tool,
                    call=call,
                    message=(
                        "发现未完成的非幂等副作用记录，"
                        "无法安全自动重试。"
                    ),
                )

        result = await self._execute_with_retry(
            tool=tool,
            call=call,
            context=context,
            idempotency_key=(
                idempotency_key
                if tool.side_effect
                else None
            ),
        )

        if (
            tool.side_effect
            and self.idempotency_store
            is not None
            and result.ok
        ):
            self.idempotency_store.complete(
                idempotency_key=idempotency_key,
                result=result,
            )

        return result

    async def _execute_with_retry(
        self,
        *,
        tool: Tool,
        call: ToolCall,
        context: ToolContext,
        idempotency_key: str | None,
    ) -> ToolResult:
        # 非幂等 Side Effect 不自动重试。
        retries = (
            tool.max_retries
            if (
                not tool.side_effect
                or tool.idempotent
            )
            else 0
        )
        max_attempts = retries + 1

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

            except TimeoutError as exc:
                if (
                    tool.side_effect
                    and not tool.idempotent
                    and idempotency_key
                    and self.idempotency_store
                    is not None
                ):
                    self.idempotency_store.mark_uncertain(
                        idempotency_key=idempotency_key,
                        error_message=(
                            "非幂等副作用 Tool 超时；"
                            "远端效果是否发生未知。"
                        ),
                    )
                    return self._reconciliation_required(
                        tool=tool,
                        call=call,
                        message=str(exc) or "tool timeout",
                        attempts=attempt,
                    )

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
                    if (
                        tool.side_effect
                        and not tool.idempotent
                        and idempotency_key
                        and self.idempotency_store
                        is not None
                    ):
                        self.idempotency_store.mark_uncertain(
                            idempotency_key=idempotency_key,
                            error_message=str(exc),
                        )
                        return self._reconciliation_required(
                            tool=tool,
                            call=call,
                            message=str(exc),
                            attempts=attempt,
                        )

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
                if (
                    tool.side_effect
                    and not tool.idempotent
                    and idempotency_key
                    and self.idempotency_store
                    is not None
                ):
                    self.idempotency_store.mark_uncertain(
                        idempotency_key=idempotency_key,
                        error_message=str(exc),
                    )
                    return self._reconciliation_required(
                        tool=tool,
                        call=call,
                        message=str(exc),
                        attempts=attempt,
                    )

                return ToolResult(
                    call_id=call.call_id,
                    tool_name=tool.name,
                    status=ToolStatus.ERROR,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                    attempts=attempt,
                )

        raise AssertionError(
            "unreachable"
        )

    async def _run_once(
        self,
        *,
        tool: Tool,
        kwargs: dict,
        context: ToolContext,
    ):
        handler_kwargs = dict(
            kwargs
        )
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

    @staticmethod
    def _reconciliation_required(
        *,
        tool: Tool,
        call: ToolCall,
        message: str,
        attempts: int = 1,
    ) -> ToolResult:
        return ToolResult(
            call_id=call.call_id,
            tool_name=tool.name,
            status=ToolStatus.RECONCILIATION_REQUIRED,
            error_code="RECONCILIATION_REQUIRED",
            error_message=message,
            attempts=attempts,
        )


class _NoopInstrument:
    def add(
        self,
        value,
        attributes=None,
    ) -> None:
        return None

    def record(
        self,
        value,
        attributes=None,
    ) -> None:
        return None

class _NoopMetrics:
    def __init__(self) -> None:
        self.tool_calls = _NoopInstrument()
        self.tool_errors = _NoopInstrument()
        self.tool_duration = _NoopInstrument()

class _NoopSpan:
    def set_attribute(
        self,
        key,
        value,
    ) -> None:
        return None

    def set_error(
        self,
        description,
    ) -> None:
        return None

class _NoopSpanContext:
    def __enter__(self):
        return _NoopSpan()

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

class _NoopObservability:
    def span(
        self,
        name,
        attributes=None,
    ):
        return _NoopSpanContext()
