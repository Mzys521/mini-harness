import asyncio

from harness.mcp.config import MCPServerConfig, MCPToolPolicy, MCPTransport
from harness.mcp.manager import MCPManager
from harness.models import ToolCall
from harness.tools.definition import ToolContext
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry

from app_tools.calculator import tool_list

async def main() -> None:
    registry = ToolRegistry()

    for tool in tool_list:
        registry.register(tool)

    manager = MCPManager([
        MCPServerConfig(
            name="demo",
            transport=MCPTransport.HTTP,
            url="http://localhost:8000/mcp",
            required=True,
            allowed_tools=frozenset({"multiply"}),
            tool_policies={
                "multiply": MCPToolPolicy(
                    side_effect=False,
                    idempotent=True,
                    max_retries=0,
                    timeout_seconds=5.0,
                )
            },
        )
    ])

    await manager.register_all_tools(registry)

    executor = ToolExecutor(registry)

    context = ToolContext(
        run_id="smoke_run",
        user_id="smoke_user",
        tenant_id="tenant_demo",
        permissions=frozenset({
            "mcp.demo.multiply",
        }),
    )

    local_result = await executor.execute(
        ToolCall(
            call_id="local_1",
            name="add",
            arguments={"a": 2, "b": 3},
        ),
        context,
    )

    mcp_result = await executor.execute(
        ToolCall(
            call_id="mcp_1",
            name="demo__multiply",
            arguments={"a": 6, "b": 7},
        ),
        context,
    )

    assert local_result.ok
    assert local_result.data == 5
    assert mcp_result.ok

    print("Smoke Test（冒烟测试）通过。")
    print("Local Tool（本地工具）：", local_result.data)
    print("MCP Tool（MCP工具）：", mcp_result.data)

if __name__ == "__main__":
    asyncio.run(main())