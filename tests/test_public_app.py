# 文件：tests/test_public_app.py
import asyncio
from dataclasses import replace

import pytest

from harness import HarnessApp, HarnessConfig, tool
from harness.models import ModelResult, ModelUsage


class FinalModel:
    async def generate(
        self,
        *,
        input_data,
        tools,
        instructions=None,
        previous_response_id=None,
    ) -> ModelResult:
        del input_data, tools, instructions, previous_response_id
        return ModelResult(
            text="ok",
            response_id="resp_public",
            usage=ModelUsage(input_tokens=3, output_tokens=1, total_tokens=4),
        )


def config_for(tmp_path):
    base = HarnessConfig()
    return replace(
        base,
        app=replace(base.app, database_path=str(tmp_path / "harness.db")),
    )


@pytest.mark.asyncio
async def test_app_tool_decorator_keeps_python_function_callable(tmp_path) -> None:
    app = HarnessApp(config_for(tmp_path), model_provider=FinalModel())

    @app.tool
    def add(a: float, b: float) -> float:
        """计算加法。"""
        return a + b

    assert add(2, 3) == 5
    runtime = await app.build()
    registered = runtime.registry.get("add")
    assert registered.description == "计算加法。"
    assert registered.input_schema["properties"]["a"]["type"] == "number"

    result = await app.ask("hello")
    assert result.output == "ok"


def test_standalone_tool_and_plain_callable_are_both_accepted(tmp_path) -> None:
    app = HarnessApp(config_for(tmp_path), model_provider=FinalModel())

    @tool(side_effect=False)
    def multiply(a: int, b: int) -> int:
        return a * b

    def subtract(a: int, b: int) -> int:
        return a - b

    app.add_tool(multiply)
    app.add_tool(subtract)
    assert multiply(3, 4) == 12
    assert {item.name for item in app._tools} == {"multiply", "subtract"}


@pytest.mark.asyncio
async def test_tool_registration_cannot_mutate_built_runtime(tmp_path) -> None:
    app = HarnessApp(config_for(tmp_path), model_provider=FinalModel())

    @app.tool
    def add(a: int, b: int) -> int:
        return a + b

    # build() 之后注册边界关闭：Tool 与 Plugin 都不再可变。
    await app.build()

    with pytest.raises(RuntimeError):
        app.add_tool(lambda value: value)


def test_local_http_app_healthz(tmp_path) -> None:
    from fastapi.testclient import TestClient

    app = HarnessApp(config_for(tmp_path), model_provider=FinalModel())
    api = asyncio.run(app.create_http_app())

    with TestClient(api) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["mode"] == "local"
