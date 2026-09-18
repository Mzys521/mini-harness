from mcp import Client , StdioServerParameters
from harness.mcp.config import MCPServerConfig , MCPTransport
from harness.mcp.errors import MCPConfigurationError , MCPConnectionError
from harness.mcp.models import MCPToolSpec
from time import perf_counter

class MCPGateway:
    """官方 MCP SDK 与 Harness Core 只见的网关"""
    def __init__(self, config, *, observability, metrics) -> None:
        self.config = config
        self.observability = observability
        self.metrics = metrics

    def _target(self):
        if self.config.transport == MCPTransport.HTTP:
            if not self.config.url:
                raise MCPConfigurationError("HTTP MCP Server 必须配置 url")
            return self.config.url
        
        if self.config.transport == MCPTransport.STDIO:
            if not self.config.command:
                 raise MCPConfigurationError("stdio MCP Server 必须配置 command")
            return StdioServerParameters(
                command=self.config.command,
                args=list(self.config.args),
                env=self.config.env or None,
            )

        raise MCPConfigurationError(f"不支持的 transport: {self.config.transport}")

    async def list_tools(self) -> list[MCPToolSpec]:
        specs: list[MCPToolSpec] = []

        try:
            async with Client(self._target()) as client:
                cursor = None

                while True:
                    result = await client.list_tools(cursor=cursor)

                    for tool in result.tools:
                        if self.config.allowed_tools is not None and tool.name not in self.config.allowed_tools:
                            continue

                        prefix = self.config.tool_prefix or self.config.name
                        raw = tool.model_dump(by_alias=True)

                        specs.append(
                            MCPToolSpec(
                                server_name=self.config.name,
                                remote_name=tool.name,
                                local_name=f"{prefix}__{tool.name}",
                                description=tool.description or "",
                                input_schema=tool.input_schema,
                                annotations=raw.get("annotations", {}) or {},
                            )
                        )

                    cursor = result.next_cursor
                    if cursor is None:
                        break

        except Exception as exc:
            raise MCPConnectionError(
                f"无法从 MCP Server '{self.config.name}' 发现工具：{exc}"
            ) from exc

        return specs

    async def call_tool(self, remote_name: str, arguments: dict):
        started = perf_counter()
        attributes = {
            "mcp.server.name": self.config.name,
            "mcp.tool.name": remote_name,
        }
        self.metrics.mcp_calls.add(1, attributes)

        with self.observability.span("mcp.tool.call", attributes) as span:
            try:
                async with Client(self._target()) as client:
                    result = await client.call_tool(remote_name, arguments)

                status = "error" if result.is_error else "success"
                span.set_attribute("mcp.tool.status", status)
                self.metrics.mcp_duration.record(
                    perf_counter() - started,
                    {**attributes, "status": status},
                )
                if result.is_error:
                    self.metrics.mcp_errors.add(1, {**attributes, "status": "tool_error"})
                return result

            except Exception as exc:
                self.metrics.mcp_errors.add(1, {**attributes, "status": "transport_error"})
                self.metrics.mcp_duration.record(
                    perf_counter() - started,
                    {**attributes, "status": "transport_error"},
                )
                span.set_error("mcp transport failure")
                raise MCPConnectionError(
                    f"MCP Tool 调用传输失败：{self.config.name}/{remote_name}: {exc}"
                ) from exc

    async def read_resource(self , url : str):
        try : 
            async with Client(self._target()) as client:
                return await client.read_resource(url)
        except Exception as exc:
            raise MCPConnectionError(
                f"无法从 MCP Server '{self.config.name}' 读取资源：{exc}"
            ) from exc




                    









