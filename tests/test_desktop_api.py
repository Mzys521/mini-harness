import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_tools.workspace import tool_list as workspace_tools
from harness import HarnessApp, HarnessConfig
from harness.models import ModelResult, ModelUsage, ToolCall
from harness.tools.definition import ToolContext


class ScriptedModel:
    """Test-only provider. All filesystem, HTTP, workers and persistence are real."""
    def __init__(self, calls=None):
        self.calls = list(calls or [])
        self.instructions = []
        self.count = 0

    async def generate(self, *, input_data, tools, instructions=None, previous_response_id=None):
        self.instructions.append(instructions)
        self.count += 1
        return ModelResult(response_id=f"response_{self.count}", text="已完成" if not self.calls else "", tool_calls=[self.calls.pop(0)] if self.calls else [], usage=ModelUsage(input_tokens=2, output_tokens=1, total_tokens=3))


def setup_app(tmp_path, model=None, transitions=16):
    base = HarnessConfig()
    config = replace(base, app=replace(base.app, database_path=str(tmp_path / "app.db"), max_steps=1), security=replace(base.security, audit_path=str(tmp_path / "audit.jsonl"), max_tool_calls_per_run=1), durable=replace(base.durable, max_transitions_per_claim=transitions))
    app = HarnessApp(config, model_provider=model or ScriptedModel())
    # 工作区工具定义在应用层 app_tools/，由入口负责注册（main.py 里是同一行）。
    app.add_tools(workspace_tools)
    api = asyncio.run(app.create_http_app())
    return app, TestClient(api)


def test_runtime_builds_when_app_tools_is_not_installed(tmp_path):
    """框架层不得依赖 app_tools。

    `app_tools` 不在发行版的 packages 列表里，因此框架任何
    `from app_tools...` 都会让 `pip install mini-harness` 之后构建运行时
    必然 ModuleNotFoundError（Phase 12 后曾经出现过一次回归）。
    """
    import builtins

    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "app_tools" or name.startswith("app_tools."):
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    base = HarnessConfig()
    config = replace(
        base,
        app=replace(base.app, database_path=str(tmp_path / "app.db")),
        security=replace(base.security, audit_path=str(tmp_path / "audit.jsonl")),
    )
    app = HarnessApp(config, model_provider=ScriptedModel())
    builtins.__import__ = guard
    try:
        api = asyncio.run(app.create_http_app())
    finally:
        builtins.__import__ = real_import
    assert api is not None


def workspace(client, root):
    response = client.post("/v1/workspaces", json={"path": str(root), "create": True})
    assert response.status_code == 201, response.text
    return response.json()


def run_worker(app):
    return asyncio.run(app.runtime.worker_pool.worker_factory(0).run_once())


def test_workspace_browse_switch_persist_and_reject_escape(tmp_path):
    app, client = setup_app(tmp_path)
    root = tmp_path / "project"
    w = workspace(client, root)
    (root / "main.py").write_text("print('hello')", encoding="utf-8")
    assert client.get("/v1/directories", params={"path": str(root)}).json()["path"] == str(root.resolve())
    assert client.get(f"/v1/workspaces/{w['id']}/files").json()["entries"][0]["name"] == "main.py"
    assert client.get(f"/v1/workspaces/{w['id']}/file", params={"path": "main.py"}).json()["content"] == "print('hello')"
    assert client.get(f"/v1/workspaces/{w['id']}/file", params={"path": "../app.db"}).status_code == 400
    _, reloaded = setup_app(tmp_path)
    assert reloaded.get("/v1/workspaces").json()["items"][0]["id"] == w["id"]
    assert client.get("/v1/runs").json()["items"] == []
    assert client.post("/v1/workspaces", json={"path": str(root)}, headers={"Origin": "https://example.com"}).status_code == 403


def test_knowledge_custom_destination_source_and_workspace_isolation(tmp_path):
    app, client = setup_app(tmp_path)
    w = workspace(client, tmp_path / "one")
    other = workspace(client, tmp_path / "two")
    destination = tmp_path / "custom-knowledge"
    assert client.patch(f"/v1/workspaces/{w['id']}/knowledge-path", json={"path": str(destination)}).status_code == 200
    response = client.post(f"/v1/workspaces/{w['id']}/knowledge/upload", params={"filename": "guide.md"}, content="可靠知识".encode(), headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 201, response.text
    assert Path(response.json()["stored_path"]).parent == destination
    source = tmp_path / "source.txt"
    source.write_text("another knowledge source", encoding="utf-8")
    assert client.post(f"/v1/workspaces/{w['id']}/knowledge/import", json={"path": str(source)}).status_code == 201
    assert len(client.get(f"/v1/workspaces/{w['id']}/knowledge").json()["items"]) == 2
    assert app.runtime.desktop.search_knowledge(w["id"], "可靠")[0]["name"] == "guide.md"
    assert app.runtime.desktop.search_knowledge(other["id"], "可靠") == []
    assert client.post(f"/v1/workspaces/{w['id']}/knowledge/upload", params={"filename": "image.bin"}, content=b"\x00\xff").status_code == 400


def test_conversation_history_and_trace_are_from_worker(tmp_path):
    app, client = setup_app(tmp_path)
    w = workspace(client, tmp_path / "project")
    session = client.post("/v1/sessions", json={"workspace_id": w["id"], "title": "检查代码"}).json()
    submitted = client.post("/v1/runs", json={"input": "请检查代码", "workspace_id": w["id"], "conversation_id": session["id"]})
    assert submitted.status_code == 202, submitted.text
    rid = submitted.json()["run_id"]
    assert run_worker(app)
    trace = client.get(f"/v1/runs/{rid}/trace").json()
    assert trace["status"] == "success"
    assert trace["totalTokens"] == 3
    assert trace["nodes"][-1]["output"] == "已完成"
    assert trace["cost"] is None
    messages = client.get(f"/v1/sessions/{session['id']}/messages").json()["items"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    another = workspace(client, tmp_path / "different")
    assert client.post("/v1/runs", json={"input": "test", "workspace_id": another["id"], "conversation_id": session["id"]}).status_code == 400


def test_write_requires_approval_and_returns_real_diff(tmp_path):
    model = ScriptedModel([ToolCall(call_id="write_1", name="workspace_write", arguments={"path": "hello.txt", "content": "after"})])
    app, client = setup_app(tmp_path, model)
    w = workspace(client, tmp_path / "project")
    target = Path(w["path"]) / "hello.txt"
    target.write_text("before", encoding="utf-8")
    rid = client.post("/v1/runs", json={"input": "修改文件", "workspace_id": w["id"]}).json()["run_id"]
    run_worker(app)
    assert client.get(f"/v1/runs/{rid}/trace").json()["status"] == "pending"
    assert target.read_text() == "before"
    assert client.post(f"/v1/runs/{rid}/approve").status_code == 202
    run_worker(app)
    assert target.read_text() == "after"
    trace = client.get(f"/v1/runs/{rid}/trace").json()
    diff = next(n["diff"] for n in trace["nodes"] if "diff" in n)
    assert diff == {"path": "hello.txt", "before": "before", "after": "after"}


def test_reject_prevents_write_and_pause_resume_delivers_instruction(tmp_path):
    model = ScriptedModel([ToolCall(call_id="write_1", name="workspace_write", arguments={"path": "hello.txt", "content": "after"})])
    app, client = setup_app(tmp_path, model)
    w = workspace(client, tmp_path / "project")
    rid = client.post("/v1/runs", json={"input": "修改文件", "workspace_id": w["id"]}).json()["run_id"]
    assert client.post(f"/v1/runs/{rid}/pause").status_code == 202
    run_worker(app)
    assert client.get(f"/v1/runs/{rid}/trace").json()["status"] == "paused"
    assert model.count == 0
    assert client.post(f"/v1/runs/{rid}/instructions", json={"text": "新增测试约束"}).status_code == 202
    assert client.post(f"/v1/runs/{rid}/resume").status_code == 202
    run_worker(app)
    assert "新增测试约束" in model.instructions[-1]
    assert client.post(f"/v1/runs/{rid}/reject").status_code == 202
    run_worker(app)
    assert client.get(f"/v1/runs/{rid}/trace").json()["status"] == "skipped"
    assert not (Path(w["path"]) / "hello.txt").exists()


def test_legacy_step_and_tool_budgets_do_not_limit_personal_runs(tmp_path):
    model = ScriptedModel([ToolCall(call_id=f"read_{i}", name="workspace_list", arguments={"path": "."}) for i in range(24)])
    app, client = setup_app(tmp_path, model)
    w = workspace(client, tmp_path / "project")
    rid = client.post("/v1/runs", json={"input": "读取项目", "workspace_id": w["id"]}).json()["run_id"]
    for _ in range(10):
        if not run_worker(app):
            break
    trace = client.get(f"/v1/runs/{rid}/trace").json()
    assert trace["status"] == "success"
    assert model.count == 25
    assert len([n for n in trace["nodes"] if n["kind"] == "tool"]) == 24


def test_checkpoint_replay_has_new_run_and_fresh_approval(tmp_path):
    model = ScriptedModel([ToolCall(call_id="write_1", name="workspace_write", arguments={"path": "hello.txt", "content": "after"})])
    app, client = setup_app(tmp_path, model)
    w = workspace(client, tmp_path / "project")
    rid = client.post("/v1/runs", json={"input": "修改文件", "workspace_id": w["id"]}).json()["run_id"]
    run_worker(app)
    trace = client.get(f"/v1/runs/{rid}/trace").json()
    tool = next(n for n in trace["nodes"] if n["kind"] == "tool")
    replay = client.post(f"/v1/runs/{rid}/replay", json={"step_id": tool["id"]})
    assert replay.status_code == 202, replay.text
    new_id = replay.json()["run_id"]
    assert new_id != rid
    run_worker(app)
    assert client.get(f"/v1/runs/{new_id}/trace").json()["parentId"] == rid
    assert client.get(f"/v1/runs/{new_id}/trace").json()["status"] == "pending"
    assert not (Path(w["path"]) / "hello.txt").exists()


def test_agent_configuration_persists_and_affects_subsequent_run(tmp_path):
    model = ScriptedModel()
    app, client = setup_app(tmp_path, model)
    assert client.put("/v1/agent", json={"name": "My Agent", "instructions": "先分析再测试"}).status_code == 200
    client.post("/v1/runs", json={"input": "hello"})
    run_worker(app)
    assert "先分析再测试" in model.instructions[0]
    _, other_client = setup_app(tmp_path)
    assert other_client.get("/v1/agent").json()["name"] == "My Agent"


def test_sessions_are_isolated_archivable_and_deletable(tmp_path):
    app, client = setup_app(tmp_path)
    w = workspace(client, tmp_path / "project")
    first = client.post("/v1/sessions", json={"workspace_id": w["id"], "title": "会话一"}).json()
    second = client.post("/v1/sessions", json={"workspace_id": w["id"], "title": "会话二"}).json()

    # 会话隔离：Run 与消息只属于自己的 conversation。
    rid = client.post("/v1/runs", json={"input": "你好", "workspace_id": w["id"], "conversation_id": first["id"]}).json()["run_id"]
    run_worker(app)
    assert [item["id"] for item in client.get("/v1/runs", params={"conversation_id": first["id"]}).json()["items"]] == [rid]
    assert client.get("/v1/runs", params={"conversation_id": second["id"]}).json()["items"] == []
    assert client.get(f"/v1/sessions/{second['id']}/messages").json()["items"] == []

    # 归档：默认列表不含归档会话，archived=true 才返回。
    assert client.patch(f"/v1/sessions/{first['id']}", json={"archived": True}).json()["archived"] == 1
    active = client.get("/v1/sessions", params={"workspace_id": w["id"]}).json()["items"]
    assert [item["id"] for item in active] == [second["id"]]
    archived = client.get("/v1/sessions", params={"workspace_id": w["id"], "archived": True}).json()["items"]
    assert [item["id"] for item in archived] == [first["id"]]
    assert client.patch(f"/v1/sessions/{first['id']}", json={"archived": False}).json()["archived"] == 0

    # 重命名与空 patch 校验。
    assert client.patch(f"/v1/sessions/{first['id']}", json={"title": "新标题"}).json()["title"] == "新标题"
    assert client.patch(f"/v1/sessions/{first['id']}", json={}).status_code == 400
    assert client.patch("/v1/sessions/conv_missing", json={"archived": True}).status_code == 404

    # 删除：Run / 步骤 / 消息 / 检查点一并清理，会话本身也随之消失。
    assert client.get(f"/v1/sessions/{first['id']}/messages").json()["items"]
    assert client.delete(f"/v1/sessions/{first['id']}").json() == {"removed": True, "runs": 1}
    assert client.get(f"/v1/sessions/{first['id']}/messages").status_code == 404
    assert client.get("/v1/runs").json()["items"] == []
    assert client.get(f"/v1/workspaces/{w['id']}/files").status_code == 200
    assert client.delete("/v1/sessions/conv_missing").status_code == 404


def test_delete_refuses_while_a_run_is_still_running(tmp_path):
    model = ScriptedModel([ToolCall(call_id="write_1", name="workspace_write", arguments={"path": "a.txt", "content": "x"})])
    app, client = setup_app(tmp_path, model)
    w = workspace(client, tmp_path / "project")
    session = client.post("/v1/sessions", json={"workspace_id": w["id"], "title": "待审批"}).json()
    rid = client.post("/v1/runs", json={"input": "写文件", "workspace_id": w["id"], "conversation_id": session["id"]}).json()["run_id"]

    run_worker(app)
    assert client.get(f"/v1/runs/{rid}/trace").json()["status"] == "pending"     # 正在等待审批
    assert client.delete(f"/v1/sessions/{session['id']}").status_code == 409

    # 拒绝后 Run 进入终态，会话才可以删除。
    assert client.post(f"/v1/runs/{rid}/reject").status_code == 202
    run_worker(app)
    assert client.delete(f"/v1/sessions/{session['id']}").status_code == 200
    assert client.get("/v1/sessions", params={"workspace_id": w["id"]}).json()["items"] == []
