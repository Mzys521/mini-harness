# 文件：harness/mcp/client.py
from time import perf_counter

from mcp import Client, StdioServerParameters

from harness.mcp.config import (
    MCPServerConfig,
    MCPTransport,
)
from harness.mcp.errors import (
    MCPConfigurationError,
    MCPConnectionError,
)
from harness.mcp.models import (
    MCPToolSpec,
)

class MCPGateway:
    """官方 MCP SDK 与 Harness Core 之间的 Anti-corruption Layer。"""

    def __init__(
        self,
        config: MCPServerConfig,
        *,
        observability=None,
        metrics=None,
    ) -> None:
        self.config = config
        self.observability = observability
        self.metrics = metrics

    def _target(self):
        if (
            self.config.transport
            == MCPTransport.HTTP
        ):
            if not self.config.url:
                raise MCPConfigurationError(
                    "HTTP MCP Server 必须配置 url"
                )
            return self.config.url

        if (
            self.config.transport
            == MCPTransport.STDIO
        ):
            if not self.config.command:
                raise MCPConfigurationError(
                    "stdio MCP Server 必须配置 command"
                )
            return StdioServerParameters(
                command=self.config.command,
                args=list(
                    self.config.args
                ),
                env=(
                    self.config.env
                    or None
                ),
            )

        raise MCPConfigurationError(
            f"不支持的 transport: {self.config.transport}"
        )

    async def list_tools(
        self,
    ) -> list[MCPToolSpec]:
        specs: list[MCPToolSpec] = []

        try:
            async with Client(
                self._target()
            ) as client:
                cursor = None

                while True:
                    result = (
                        await client.list_tools(
                            cursor=cursor
                        )
                    )

                    for tool in result.tools:
                        if (
                            self.config.allowed_tools
                            is not None
                            and tool.name
                            not in self.config.allowed_tools
                        ):
                            continue

                        prefix = (
                            self.config.tool_prefix
                            or self.config.name
                        )
                        raw = tool.model_dump(
                            by_alias=True
                        )

                        specs.append(
                            MCPToolSpec(
                                server_name=self.config.name,
                                remote_name=tool.name,
                                local_name=(
                                    f"{prefix}__{tool.name}"
                                ),
                                description=(
                                    tool.description
                                    or ""
                                ),
                                input_schema=(
                                    tool.input_schema
                                ),
                                annotations=(
                                    raw.get(
                                        "annotations",
                                        {},
                                    )
                                    or {}
                                ),
                            )
                        )

                    cursor = (
                        result.next_cursor
                    )
                    if cursor is None:
                        break

        except Exception as exc:
            raise MCPConnectionError(
                "无法从 MCP Server "
                f"'{self.config.name}' 发现工具：{exc}"
            ) from exc

        return specs

    async def call_tool(
        self,
        remote_name: str,
        arguments: dict,
    ):
        started = perf_counter()
        attributes = {
            "mcp.server.name": (
                self.config.name
            ),
            "mcp.tool.name": remote_name,
        }

        if self.metrics is not None:
            self.metrics.mcp_calls.add(
                1,
                attributes,
            )

        span_context = (
            self.observability.span(
                "mcp.tool.call",
                attributes,
            )
            if self.observability is not None
            else _NullSpanContext()
        )

        with span_context as span:
            try:
                async with Client(
                    self._target()
                ) as client:
                    result = (
                        await client.call_tool(
                            remote_name,
                            arguments,
                        )
                    )

                status = (
                    "error"
                    if result.is_error
                    else "success"
                )
                span.set_attribute(
                    "mcp.tool.status",
                    status,
                )

                if self.metrics is not None:
                    self.metrics.mcp_duration.record(
                        perf_counter() - started,
                        {
                            **attributes,
                            "status": status,
                        },
                    )
                    if result.is_error:
                        self.metrics.mcp_errors.add(
                            1,
                            {
                                **attributes,
                                "status": "tool_error",
                            },
                        )

                return result

            except Exception as exc:
                if self.metrics is not None:
                    self.metrics.mcp_errors.add(
                        1,
                        {
                            **attributes,
                            "status": "transport_error",
                        },
                    )
                    self.metrics.mcp_duration.record(
                        perf_counter() - started,
                        {
                            **attributes,
                            "status": "transport_error",
                        },
                    )

                span.record_exception(exc)
                span.set_error(
                    "mcp transport failure"
                )
                raise MCPConnectionError(
                    "MCP Tool 调用传输失败："
                    f"{self.config.name}/"
                    f"{remote_name}: {exc}"
                ) from exc

    async def read_resource(
        self,
        uri: str,
    ):
        try:
            async with Client(
                self._target()
            ) as client:
                return await client.read_resource(
                    uri
                )
        except Exception as exc:
            raise MCPConnectionError(
                "MCP Resource 读取失败："
                f"{self.config.name}/{uri}: {exc}"
            ) from exc

class _NullSpan:
    def set_attribute(
        self,
        key,
        value,
    ) -> None:
        return None

    def record_exception(
        self,
        exc,
    ) -> None:
        return None

    def set_error(
        self,
        description,
    ) -> None:
        return None

class _NullSpanContext:
    def __enter__(self):
        return _NullSpan()

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False
