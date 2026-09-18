import pytest

from app_tools.calculator import tool_list
from harness.models import ToolCall
from harness.tools.definition import ToolContext
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry
from tests.fakes_observability import FakeMetrics, FakeObservability

@pytest.mark.asyncio
async def test_tool_executor_creates_span() -> None:
    registry = ToolRegistry()

    for tool in tool_list:
        registry.register(tool)
    observability = FakeObservability()
    metrics = FakeMetrics()
    executor = ToolExecutor(
        registry,
        observability=observability,
        metrics=metrics,
    )

    result = await executor.execute(
        ToolCall(
            call_id="call_1",
            name="add",
            arguments={"a": 2, "b": 3},
        ),
        ToolContext(run_id="run_1"),
    )

    assert result.ok
    assert "tool.execute" in observability.span_names
    assert metrics.tool_calls.values