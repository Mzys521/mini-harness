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
        self.gateways = {
            config.name: MCPGateway(
                config,
                observability=observability,
                metrics=metrics,
            )
            for config in configs
            if config.enabled
        }

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
