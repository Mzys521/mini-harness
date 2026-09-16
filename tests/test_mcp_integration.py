import pytest
from mcp import Client

from mcp_servers.demo_server import mcp

@pytest.mark.asyncio
async def test_real_mcp_server_in_process() -> None:
    async with Client(
        mcp,
        raise_exceptions=True,
    ) as client:
        result = await client.list_tools()

        names = {
            tool.name
            for tool in result.tools
        }

        assert "multiply" in names

        call_result = await client.call_tool(
            "multiply",
            {"a": 6, "b": 7},
        )

        assert call_result.is_error is False