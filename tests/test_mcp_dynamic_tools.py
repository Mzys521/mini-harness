"""运行期工具注册：注册表动态层、按 Run 快照、MCP Server 登记接口。

`harness/mcp/client.py` 延迟导入官方 SDK，因此本文件**不需要 `[mcp]` extra**：
管理器级别的用例用替身网关覆盖真实 `MCPManager` 的注册 / 摘除逻辑；
注册表与快照逻辑则完全不依赖 extra。

组合根在 `_register_mcp` 里另有一次显式 `import mcp` 检查，保证「启用 MCP 但没装
extra」仍在**构建期**就抛出带安装命令的 `FeatureDependencyError`。
"""
import asyncio
import importlib.util
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from harness import HarnessApp, HarnessConfig
from harness.app.mcp_api import MCPServerInput, create_server_config
from harness.mcp.config import UNTRUSTED_TOOL_POLICY, MCPServerConfig, MCPTransport
from harness.mcp.store import SQLiteMCPServerStore
from harness.models import ToolCall
from harness.persistence.database import Database
from harness.tools.definition import Tool, ToolContext
from harness.tools.errors import ToolNotFoundError
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry


class StubModel:
    async def generate(self, **kwargs):
        raise AssertionError("本用例不调用模型")


def sample_tool(name: str, *, source: str = "local", server: str | None = None) -> Tool:
    metadata = {"mcp_server": server} if server else {}
    return Tool(
        name=name,
        description="测试工具",
        input_schema={"type": "object", "properties": {}},
        handler=lambda **kwargs: "ok",
        source=source,
        metadata=metadata,
    )


class FakeMCPGateway:
    """替身网关：不连远端，只按配置返回一个固定的远端工具声明。

    它替换 `harness.mcp.manager.MCPGateway`，因此下面的用例跑的是**真实
    `MCPManager`**（注册 / 摘除 / 工具归属），只有「连远端」这一层是假的。
    """

    def __init__(self, config, *, observability=None, metrics=None) -> None:
        self.config = config
        self.observability = observability
        self.metrics = metrics

    async def list_tools(self):
        return [
            SimpleNamespace(
                remote_name="echo",
                local_name=f"{self.config.name}_echo",
                server_name=self.config.name,
                description="回显",
                input_schema={"type": "object", "properties": {}},
                annotations={},
            )
        ]


def build_manager(monkeypatch):
    """把真实 MCPManager 的网关换成替身。"""
    from harness.mcp import manager as manager_module

    monkeypatch.setattr(manager_module, "MCPGateway", FakeMCPGateway)
    return manager_module.MCPManager([])


def build_client(tmp_path, *, manager=None, registry=None):
    base = HarnessConfig()
    config = replace(
        base,
        app=replace(base.app, database_path=str(tmp_path / "app.db")),
    )
    app = HarnessApp(config, model_provider=StubModel())
    api = asyncio.run(app.create_http_app())

    if manager is not None:
        app.runtime.mcp = manager
    if registry is not None:
        app.runtime.registry = registry
    app.runtime.mcp_store = SQLiteMCPServerStore(app.runtime.database)
    return app, TestClient(api)


# ---- 注册表：构建期封板 + 运行期动态层 ----


def test_registry_freezes_build_time_registration():
    registry = ToolRegistry()
    registry.register(sample_tool("build_time"))
    registry.freeze()

    with pytest.raises(ValueError):
        registry.register(sample_tool("late"))

    # 动态注册仍然允许，并且可以被摘除。
    registry.register(sample_tool("dynamic", server="srv"), dynamic=True)
    assert registry.is_dynamic("dynamic") is True
    assert registry.is_dynamic("build_time") is False

    registry.unregister("dynamic")
    with pytest.raises(ToolNotFoundError):
        registry.get("dynamic")

    # 构建期工具不允许摘除，重复摘除则是幂等的。
    with pytest.raises(ValueError):
        registry.unregister("build_time")
    registry.unregister("never_registered")


def test_schemas_can_be_filtered_by_snapshot():
    registry = ToolRegistry()
    registry.register(sample_tool("alpha"))
    registry.register(sample_tool("beta"))

    assert {item["name"] for item in registry.openai_schemas()} == {"alpha", "beta"}
    assert [
        item["name"] for item in registry.openai_schemas(frozenset({"beta"}))
    ] == ["beta"]
    assert registry.openai_schemas(frozenset()) == []


async def test_executor_rejects_tools_outside_the_run_snapshot():
    registry = ToolRegistry()
    registry.register(sample_tool("alpha"))
    executor = ToolExecutor(registry)

    inside = await executor.execute(
        ToolCall(call_id="call_1", name="alpha", arguments={}),
        ToolContext(run_id="run_1", tool_names=frozenset({"alpha"})),
    )
    assert inside.ok is True

    outside = await executor.execute(
        ToolCall(call_id="call_2", name="alpha", arguments={}),
        ToolContext(run_id="run_1", tool_names=frozenset({"beta"})),
    )
    assert outside.status.value == "not_found"
    assert outside.error_code == "TOOL_NOT_IN_RUN_SNAPSHOT"

    # 没有快照（不经过 Runner 的直接调用）保持旧行为：不限制。
    unrestricted = await executor.execute(
        ToolCall(call_id="call_3", name="alpha", arguments={}),
        ToolContext(run_id="run_1"),
    )
    assert unrestricted.ok is True


def test_run_snapshot_is_written_into_durable_state(tmp_path):
    """Runner 创建 Run 时把当时的工具集合写进 ToolContext，并进入序列化。"""
    from harness.durable.serialization import (
        execution_from_dict,
        execution_to_dict,
    )

    base = HarnessConfig()
    config = replace(
        base,
        app=replace(base.app, database_path=str(tmp_path / "app.db")),
    )
    app = HarnessApp(config, model_provider=StubModel())
    asyncio.run(app.build())

    registry = app.runtime.registry
    registry.register(sample_tool("mcp_added_at_runtime", server="srv"), dynamic=True)

    execution = app.runtime.application.runner.create_execution(
        "你好",
        history=[],
        tool_context=ToolContext(run_id="run_snapshot"),
    )
    assert "mcp_added_at_runtime" in execution.tool_context.tool_names

    restored = execution_from_dict(execution_to_dict(execution))
    assert restored.tool_context.tool_names == execution.tool_context.tool_names


# ---- MCP Server 持久化 ----


def test_mcp_server_store_round_trip(tmp_path):
    store = SQLiteMCPServerStore(Database(str(tmp_path / "mcp.db")))

    config = MCPServerConfig(
        name="demo",
        transport=MCPTransport.STDIO,
        command="python",
        args=("-m", "demo"),
        env={"TOKEN": "x"},
        allowed_tools=frozenset({"echo"}),
        tool_prefix="demo",
    )
    store.create_server(config, created_at="2026-09-21T00:00:00")

    restored = store.get_server("demo")
    assert restored is not None
    assert restored.transport is MCPTransport.STDIO
    assert restored.command == "python"
    assert restored.args == ("-m", "demo")
    assert restored.env == {"TOKEN": "x"}
    assert restored.allowed_tools == frozenset({"echo"})
    assert [item.name for item in store.get_servers()] == ["demo"]

    assert store.delete_server("demo") is True
    assert store.delete_server("demo") is False
    assert store.get_servers() == []


# ---- 请求体校验与保守默认策略 ----


def test_server_input_requires_transport_specific_fields():
    with pytest.raises(ValueError):
        create_server_config(MCPServerInput(name="no-url", transport="http"))
    with pytest.raises(ValueError):
        create_server_config(MCPServerInput(name="no-command", transport="stdio"))


def test_dynamically_registered_servers_use_the_untrusted_default_policy():
    """远端工具声明不被信任：登记时默认「有副作用 + 需要审批」。"""
    config = create_server_config(
        MCPServerInput(
            name="remote",
            transport="http",
            url="http://127.0.0.1:9999/mcp",
        )
    )

    assert config.default_tool_policy is UNTRUSTED_TOOL_POLICY
    assert config.default_tool_policy.side_effect is True
    assert config.default_tool_policy.requires_approval is True


# ---- HTTP 接口 ----


def test_mcp_api_registers_and_removes_servers(tmp_path, monkeypatch):
    """端到端：前端提交 → 真实 MCPManager 发现并注册 → 落库 → 摘除。

    只有「连远端」是替身，注册表动态层、工具归属、持久化与 HTTP 契约都是真的。
    """
    registry = ToolRegistry()
    manager = build_manager(monkeypatch)
    app, client = build_client(tmp_path, manager=manager, registry=registry)

    with client:
        created = client.post(
            "/v1/mcp/servers",
            json={"name": "remote", "transport": "http", "url": "http://127.0.0.1:9999/mcp"},
        )
        assert created.status_code == 201
        assert created.json()["tools"] == ["remote_echo"]

        # 工具真的进了注册表的动态层，且按不可信默认策略注册。
        tool = registry.get("remote_echo")
        assert registry.is_dynamic("remote_echo") is True
        assert tool.side_effect is True
        assert tool.requires_approval is True

        listed = client.get("/v1/mcp/servers").json()["items"]
        assert [item["name"] for item in listed] == ["remote"]
        assert listed[0]["tools"] == ["remote_echo"]
        assert listed[0]["removable"] is True

        # 落库了，重启后还能回来
        assert [item.name for item in app.runtime.mcp_store.get_servers()] == ["remote"]

        removed = client.delete("/v1/mcp/servers/remote")
        assert removed.status_code == 200
        assert removed.json()["removed_tools"] == ["remote_echo"]
        assert app.runtime.mcp_store.get_servers() == []
        with pytest.raises(ToolNotFoundError):
            registry.get("remote_echo")

        assert client.get("/v1/mcp/servers").json()["items"] == []
        assert client.delete("/v1/mcp/servers/remote").status_code == 404


def test_mcp_api_rejects_static_servers_and_missing_fields(tmp_path, monkeypatch):
    registry = ToolRegistry()
    # 构建期注册的同名工具：属于 harness.toml 静态配置，不能运行期删除。
    registry.register(sample_tool("static_echo", source="mcp", server="static"))
    manager = build_manager(monkeypatch)
    manager.gateways["static"] = FakeMCPGateway(
        MCPServerConfig(name="static", transport=MCPTransport.HTTP, url="http://x")
    )
    _, client = build_client(tmp_path, manager=manager, registry=registry)

    with client:
        assert client.delete("/v1/mcp/servers/static").status_code == 400
        assert (
            client.post(
                "/v1/mcp/servers",
                json={"name": "bad", "transport": "http"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/v1/mcp/servers",
                json={"name": "bad name!", "transport": "http", "url": "http://x"},
            ).status_code
            == 422
        )


def test_mcp_api_reports_disabled_extension(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        response = client.get("/v1/mcp/servers")
        assert response.status_code == 503
        assert "[mcp]" in response.json()["detail"]


def test_enabling_mcp_without_the_extra_fails_at_build_time(tmp_path):
    """延迟导入 SDK 之后，装配期检查必须仍在：启用 MCP 但没装 extra 要在构建时失败。

    否则「没装依赖」会退化成第一次发现工具才报错——那时已经跑在 Worker 里了。
    """
    from harness.app.errors import FeatureDependencyError

    base = HarnessConfig()
    config = replace(
        base,
        mcp=replace(base.mcp, enabled=True),
        app=replace(base.app, database_path=str(tmp_path / "app.db")),
    )
    app = HarnessApp(config, model_provider=StubModel())

    if importlib.util.find_spec("mcp") is not None:
        pytest.skip("本环境装了 [mcp] extra，无法验证缺依赖路径")

    with pytest.raises(FeatureDependencyError) as error:
        asyncio.run(app.build())

    assert error.value.feature == "mcp"
    assert "[mcp]" in error.value.install_hint


# ---- 真实管理器（替身网关，不连远端，也不需要 [mcp] extra）----


def test_manager_registers_and_removes_dynamic_tools(monkeypatch):
    """真实 MCPManager 的运行期注册与摘除（替身网关，不连远端）。

    注册表已 `freeze()`，因此这里同时验证「运行期注册必须走 dynamic 层」。
    """
    registry = ToolRegistry()
    registry.freeze()
    manager = build_manager(monkeypatch)

    config = MCPServerConfig(
        name="srv",
        transport=MCPTransport.HTTP,
        url="http://127.0.0.1:9999/mcp",
        default_tool_policy=UNTRUSTED_TOOL_POLICY,
    )
    count = asyncio.run(manager.register_server(config, registry))

    assert count == 1
    tool = registry.get("srv_echo")
    # 未声明的远端工具按不可信处理：有副作用且需要审批。
    assert tool.side_effect is True
    assert tool.requires_approval is True
    assert registry.is_dynamic("srv_echo") is True

    # 同名 Server 不允许重复登记
    with pytest.raises(ValueError):
        asyncio.run(manager.register_server(config, registry))

    assert manager.unregister_server(registry, "srv") == ["srv_echo"]
    with pytest.raises(ToolNotFoundError):
        registry.get("srv_echo")
