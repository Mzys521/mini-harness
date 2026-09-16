import asyncio

from harness.mcp.client import MCPGateway
from harness.mcp.discovery import discover_and_register

class MCPManager:
    def __init__(self, configs) -> None:
        self.gateways = {
            config.name: MCPGateway(config)
            for config in configs
            if config.enabled
        }

    async def register_all_tools(self, registry) -> dict[str, int]:
        async def one(name, gateway):
            try:
                count = await discover_and_register(
                    gateway=gateway,
                    registry=registry,
                )
                return name, count, None
            except Exception as exc:
                return name, 0, exc

        results: dict[str, int] = {}

        for name, count, error in await asyncio.gather(
            *(one(name, gateway) for name, gateway in self.gateways.items())
        ):
            if error is not None:
                if self.gateways[name].config.required:
                    raise RuntimeError(
                        f"Required MCP Server 启动失败：{name}"
                    ) from error

                # Optional Dependency（可选依赖）失败时先降级运行。
                print(
                    f"[mcp.discovery.failed] server={name} error={error}"
                )
                continue

            results[name] = count

        return results