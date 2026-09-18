import asyncio

from app_tools.calculator import tool_list
from harness.models import ToolCall
from harness.observability.bootstrap import configure_observability
from harness.observability.config import ObservabilityConfig
from harness.observability.metrics import HarnessMetrics
from harness.observability.service import Observability
from harness.tools.definition import ToolContext
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry

async def main() -> None:
    configure_observability(
        ObservabilityConfig(exporter="console")
    )
    observability = Observability()
    metrics = HarnessMetrics(observability)

    registry = ToolRegistry()
    for tool in tool_list:
        registry.register(tool)
    executor = ToolExecutor(
        registry,
        observability=observability,
        metrics=metrics,
    )

    with observability.span("smoke.run"):
        result = await executor.execute(
            ToolCall(
                call_id="smoke_call",
                name="add",
                arguments={"a": 2, "b": 3},
            ),
            ToolContext(run_id="smoke_run"),
        )
        assert result.ok
        assert result.data == 5

    print("Observability Smoke Test（可观测性冒烟测试）通过。")

if __name__ == "__main__":
    asyncio.run(main())