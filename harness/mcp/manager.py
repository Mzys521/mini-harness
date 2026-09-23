# 文件：harness/mcp/manager.py
import asyncio
import logging

from harness.mcp.client import MCPGateway
from harness.mcp.discovery import (
    discover_and_register,
)

logger = logging.getLogger(
    __name__
)

class MCPManager:
    def __init__(
        self,
        configs,
        *,
        observability=None,
        metrics=None,
    ) -> None:
        self.observability = observability
        self.metrics = metrics
        self.gateways = {
            config.name: MCPGateway(
                config,
                observability=observability,
                metrics=metrics,
            )
            for config in configs
            if config.enabled
        }

    def get_server_tools(
        self,
        registry,
        name: str,
    ) -> list[str]:
        """列出某个 MCP Server 贡献的工具名（按 Tool.metadata 归属）。"""
        return [
            tool.name
            for tool in registry.list_tools()
            if tool.metadata.get("mcp_server") == name
        ]

    async def register_server(
        self,
        config,
        registry,
    ) -> int:
        """运行期登记一个 MCP Server：建网关 → 发现工具 → 注册到动态层。

        工具注册为 dynamic，因此只对被登记之后创建的 Run 生效；已经在跑的 Run 用的是
        创建时写入 ToolContext 的能力快照。发现失败会向上抛，调用方据此不落库。
        """
        if config.name in self.gateways:
            raise ValueError(f"MCP Server 已存在：{config.name}")

        gateway = MCPGateway(
            config,
            observability=self.observability,
            metrics=self.metrics,
        )
        count = await discover_and_register(
            gateway=gateway,
            registry=registry,
            dynamic=True,
        )
        self.gateways[config.name] = gateway
        return count

    def unregister_server(
        self,
        registry,
        name: str,
    ) -> list[str]:
        """摘除一个运行期登记的 MCP Server 及其工具。

        静态配置（harness.toml）的 Server 不在此列：它的工具是构建期注册的，
        摘除会破坏「能力在运行开始前确定」，因此直接拒绝。
        """
        gateway = self.gateways.get(name)
        if gateway is None:
            return []

        names = self.get_server_tools(registry, name)
        static = [
            tool_name
            for tool_name in names
            if not registry.is_dynamic(tool_name)
        ]
        if static:
            raise ValueError(
                f"MCP Server {name} 来自 harness.toml 静态配置，"
                "不能在运行期删除；请从配置文件中移除。"
            )

        for tool_name in names:
            registry.unregister(tool_name)
        del self.gateways[name]
        return names

    async def register_all_tools(
        self,
        registry,
    ) -> dict[str, int]:
        async def one(
            name,
            gateway,
        ):
            try:
                count = (
                    await discover_and_register(
                        gateway=gateway,
                        registry=registry,
                    )
                )
                return (
                    name,
                    count,
                    None,
                )
            except Exception as exc:
                return (
                    name,
                    0,
                    exc,
                )

        results: dict[str, int] = {}

        # MCP discovery 是启动期并发 I/O；单个 optional server 失败不拖垮整体。
        items = await asyncio.gather(
            *(
                one(
                    name,
                    gateway,
                )
                for name, gateway
                in self.gateways.items()
            )
        )

        for (
            name,
            count,
            error,
        ) in items:
            if error is not None:
                if (
                    self.gateways[
                        name
                    ].config.required
                ):
                    raise RuntimeError(
                        "Required MCP Server "
                        f"启动失败：{name}"
                    ) from error

                logger.warning(
                    "optional MCP discovery failed",
                    extra={
                        "mcp_server": name,
                        "error_type": (
                            type(error).__name__
                        ),
                    },
                )
                continue

            results[name] = count

        return results
