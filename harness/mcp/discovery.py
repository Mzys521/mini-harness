from harness.mcp.adapter import adapt_mcp_tool
from harness.mcp.config import MCPToolPolicy

async def discover_and_register( * , gateway , registry ) -> int:
    specs = await gateway.list_tools()
    count = 0

    for spec in specs : 
        policy = gateway.config.tool_policies.get(
            spec.remote_name,
            MCPToolPolicy()
        )

        registry.register(
            adapt_mcp_tool(
                spec=spec,
                gateway=gateway,
                policy=policy,
            )
        )
        count += 1

    return count