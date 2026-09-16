import pytest

from harness.mcp.adapter import adapt_mcp_tool
from harness.mcp.config import MCPToolPolicy
from harness.models import ToolCall
from harness.tools.definition import ToolContext
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry

from tests.fakes_mcp import FakeMCPGateway

@pytest.mark.asyncio
async def test_invalid_arguments_never_reach_remote_server() -> None:
    gateway = FakeMCPGateway()
    spec = (await gateway.list_tools())[0]

    tool = adapt_mcp_tool(
        spec=spec,
        gateway=gateway,
        policy=MCPToolPolicy(
            side_effect=False,
            idempotent=True,
        ),
    )

    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    result = await executor.execute(
        ToolCall(
            call_id="call_1",
            name="fake__multiply",
            arguments={
                "a": "wrong",
                "b": 2,
            },
        ),
        ToolContext(
            run_id="run_1",
            permissions=frozenset({
                "mcp.fake.multiply"
            }),
        ),
    )

    assert result.ok is False
    assert gateway.calls == []

@pytest.mark.asyncio
async def test_permission_denied_never_reaches_remote_server() -> None:
    gateway = FakeMCPGateway()
    spec = (await gateway.list_tools())[0]

    tool = adapt_mcp_tool(
        spec=spec,
        gateway=gateway,
        policy=MCPToolPolicy(
            side_effect=False,
        ),
    )

    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    result = await executor.execute(
        ToolCall(
            call_id="call_2",
            name="fake__multiply",
            arguments={"a": 2, "b": 3},
        ),
        ToolContext(
            run_id="run_1",
            permissions=frozenset(),
        ),
    )

    assert result.ok is False
    assert gateway.calls == []