# 文件：harness/app/mcp_api.py
"""前端登记 MCP Server 的本地 HTTP 接口。

提交一个 MCP Server 后，后端自动完成：建网关 → 发现远端工具 → 注册进工具注册表的
**动态层**。动态注册只影响之后创建的 Run（每个 Run 创建时会快照当时的工具集合），
因此不需要重建 Runtime，也不破坏「能力在运行开始前确定」。

只注册路由，不注册中间件与异常处理器：错误映射与同源保护由
`install_desktop_routes` 统一提供，因此本模块必须在它之后安装。
"""
from fastapi import Body, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from harness.mcp.config import (
    UNTRUSTED_TOOL_POLICY,
    MCPServerConfig,
    MCPTransport,
)
from harness.state.models import utc_now

_MCP_HINT = (
    "MCP 未启用：请安装 mini-harness[mcp] 并在 harness.toml 打开 [mcp].enabled。"
)


class MCPServerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    transport: str = Field(default="http", pattern="^(http|stdio)$")
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    tool_prefix: str | None = None
    allowed_tools: list[str] | None = None


def create_server_config(body: MCPServerInput) -> MCPServerConfig:
    """请求体 → MCPServerConfig，并校验该传输方式必需的字段。"""
    transport = MCPTransport(body.transport)
    if transport is MCPTransport.HTTP and not body.url:
        raise ValueError("transport=http 时必须提供 url。")
    if transport is MCPTransport.STDIO and not body.command:
        raise ValueError("transport=stdio 时必须提供 command。")

    return MCPServerConfig(
        name=body.name,
        transport=transport,
        url=body.url,
        command=body.command,
        args=tuple(body.args),
        env=dict(body.env),
        tool_prefix=body.tool_prefix,
        allowed_tools=(
            None
            if body.allowed_tools is None
            else frozenset(body.allowed_tools)
        ),
        default_tool_policy=UNTRUSTED_TOOL_POLICY,
    )


def register_mcp_routes(api, harness_app, runtime):
    def require_manager():
        # 在调用时读取 runtime（而不是注册时捕获），测试可以注入替身 manager。
        manager = runtime.mcp
        if manager is None:
            raise HTTPException(status_code=503, detail=_MCP_HINT)
        return manager

    def describe(name: str) -> dict:
        manager = require_manager()
        gateway = manager.gateways[name]
        config = gateway.config
        tools = manager.get_server_tools(runtime.registry, name)
        return {
            "name": name,
            "transport": config.transport.value,
            "url": config.url,
            "command": config.command,
            "tool_prefix": config.tool_prefix,
            "tools": tools,
            # 构建期（harness.toml）配置的 Server 不能在运行期删除。
            "removable": all(
                runtime.registry.is_dynamic(tool_name)
                for tool_name in tools
            ),
        }

    @api.get("/v1/mcp/servers")
    def get_servers():
        active = require_manager()
        return {
            "items": [
                describe(name)
                for name in sorted(active.gateways)
            ]
        }

    @api.post("/v1/mcp/servers", status_code=201)
    async def create_server(body: MCPServerInput = Body(...)):
        """登记并立即发现工具；发现失败则不落库，避免留下连不上的配置。"""
        active = require_manager()
        config = create_server_config(body)

        count = await active.register_server(
            config,
            runtime.registry,
        )
        runtime.mcp_store.create_server(
            config,
            created_at=utc_now().isoformat(),
        )
        return {
            "name": config.name,
            "tools": active.get_server_tools(
                runtime.registry,
                config.name,
            ),
            "tool_count": count,
        }

    @api.delete("/v1/mcp/servers/{name}")
    def delete_server(name: str):
        active = require_manager()
        if name not in active.gateways:
            raise LookupError(f"MCP Server 不存在：{name}")
        removed = active.unregister_server(
            runtime.registry,
            name,
        )
        runtime.mcp_store.delete_server(name)
        return {
            "name": name,
            "removed_tools": removed,
        }
