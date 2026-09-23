from harness.mcp.adapter import adapt_mcp_tool


async def discover_and_register( * , gateway , registry , dynamic : bool = False ) -> int:
    """发现远端工具并注册进注册表。

    参数 dynamic: True 表示这是运行期登记（前端新增 MCP Server）。这类工具走注册表的
    动态层，并且只对之后创建的 Run 生效——每个 Run 在创建时都会快照当时的工具集合。
    """
    specs = await gateway.list_tools()
    count = 0

    for spec in specs : 
        policy = gateway.config.tool_policies.get(
            spec.remote_name,
            gateway.config.default_tool_policy
        )

        registry.register(
            adapt_mcp_tool(
                spec=spec,
                gateway=gateway,
                policy=policy,
            ),
            dynamic=dynamic,
        )
        count += 1

    return count
