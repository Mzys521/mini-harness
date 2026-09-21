"""Run 事件流：模型增量、工具调用与终态必须实时到达客户端。

这里用 httpx 的 ASGITransport + 真实 lifespan 跑整条链路：Worker 与 SSE 在同一个
事件循环里，因此和浏览器看到的行为一致（回放缓冲、增量下发、终态关闭）。
"""
import asyncio
import json
from dataclasses import replace

import httpx
import uvicorn

from app_tools.workspace import tool_list as workspace_tools
from harness import HarnessApp, HarnessConfig
from harness.models import ModelResult, ModelUsage, ToolCall
from harness.streaming import RunEventBroker


class StreamingModel:
    """具备真实增量语义的测试 Provider：逐段回调，最后返回完整结果。"""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0

    async def generate(self, *, input_data, tools, instructions=None, previous_response_id=None, on_delta=None):
        script = self.scripts.pop(0)
        self.calls += 1
        for chunk in script["deltas"]:
            if on_delta is not None:
                on_delta(chunk)
            # 让订阅者真的“边跑边收”，而不是等整轮结束再一次拿到全部内容。
            await asyncio.sleep(0.02)
        return ModelResult(
            response_id=f"response_{self.calls}",
            text="".join(script["deltas"]),
            tool_calls=script.get("tool_calls", []),
            usage=ModelUsage(input_tokens=2, output_tokens=1, total_tokens=3),
        )


def build_app(tmp_path, model) -> HarnessApp:
    base = HarnessConfig()
    config = replace(
        base,
        app=replace(base.app, database_path=str(tmp_path / "app.db"), max_steps=4),
        security=replace(base.security, audit_path=str(tmp_path / "audit.jsonl")),
        durable=replace(base.durable, poll_interval_seconds=0.01, idle_backoff_seconds=0.01),
    )
    app = HarnessApp(config, model_provider=model)
    # 工具定义在应用层 app_tools/，入口负责注册（main.py 是同一行）。
    app.add_tools(workspace_tools)
    return app


async def read_stream(client, run_id: str, *, stop_at_end: bool = True) -> list[dict]:
    """读取 SSE 帧直到终态（或流被关闭）。"""
    events: list[dict] = []
    async with client.stream("GET", f"/v1/runs/{run_id}/stream") as response:
        assert response.status_code == 200, response.status_code
        assert response.headers["content-type"].startswith("text/event-stream")
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: "):])
            events.append(event)
            if stop_at_end and event["type"] == "run.end":
                break
    return events


async def prepare(client, tmp_path):
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    (root / "main.py").write_text("print(1)", encoding="utf-8")
    workspace = (await client.post("/v1/workspaces", json={"path": str(root), "create": True})).json()
    submitted = await client.post("/v1/runs", json={"input": "读取项目", "workspace_id": workspace["id"]})
    assert submitted.status_code == 202, submitted.text
    return submitted.json()["run_id"]


async def test_stream_reports_model_deltas_tool_calls_and_completion(tmp_path) -> None:
    model = StreamingModel([
        {"deltas": ["先读", "文件。"], "tool_calls": [ToolCall(call_id="call_1", name="workspace_read", arguments={"path": "main.py"})]},
        {"deltas": ["# 完成", "\n\n已读取。"]},
    ])
    app = build_app(tmp_path, model)
    api = await app.create_http_app()

    async with api.router.lifespan_context(api):
        transport = httpx.ASGITransport(app=api)
        async with httpx.AsyncClient(transport=transport, base_url="http://local") as client:
            run_id = await prepare(client, tmp_path)
            events = await asyncio.wait_for(read_stream(client, run_id), timeout=30)

    kinds = [event["type"] for event in events]
    assert kinds[0] == "run.submitted"
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
    assert kinds[-1] == "run.end"
    assert {"model.start", "model.delta", "model.end", "tool.start", "tool.end"} <= set(kinds)

    deltas = "".join(event["text"] for event in events if event["type"] == "model.delta")
    assert deltas == "先读文件。# 完成\n\n已读取。"

    tool_end = next(event for event in events if event["type"] == "tool.end")
    assert tool_end["status"] == "success"
    assert json.loads(tool_end["output"])["data"]["content"] == "print(1)"
    assert events[-1]["status"] == "completed"
    assert events[-1]["output"] == "# 完成\n\n已读取。"


async def test_deltas_arrive_over_real_http_while_the_run_is_running(tmp_path) -> None:
    """真正的增量验证：必须走真实 HTTP，而不是会被整体缓冲的 ASGI 传输层。

    Worker 与 SSE 在同一个事件循环里，所以这段同时证明「模型流式不阻塞事件循环」。
    """
    model = StreamingModel([{"deltas": ["a"] * 12}])
    app = build_app(tmp_path, model)
    api = await app.create_http_app()

    server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=0, log_level="warning"))
    serving = asyncio.create_task(server.serve())
    try:
        for _ in range(500):
            if server.started:
                break
            await asyncio.sleep(0.01)
        assert server.started, "uvicorn did not start"

        port = server.servers[0].sockets[0].getsockname()[1]
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
            run_id = await prepare(client, tmp_path)
            seen = 0
            async with client.stream("GET", f"/v1/runs/{run_id}/stream") as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[len("data: "):])
                    seen += 1
                    if event["type"] != "model.delta":
                        continue
                    # 第一段增量到达时整轮尚未结束：这正是“边生成边显示”。
                    assert app.runtime.durable_store.get(run_id).status.value != "completed"
                    break
                else:
                    raise AssertionError("the stream never delivered a model.delta")
            assert seen >= 1
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=30)


async def test_late_subscriber_replays_the_whole_run(tmp_path) -> None:
    model = StreamingModel([{"deltas": ["完成"]}])
    app = build_app(tmp_path, model)
    api = await app.create_http_app()

    async with api.router.lifespan_context(api):
        transport = httpx.ASGITransport(app=api)
        async with httpx.AsyncClient(transport=transport, base_url="http://local") as client:
            run_id = await prepare(client, tmp_path)
            first = await asyncio.wait_for(read_stream(client, run_id), timeout=30)
            # 运行结束后再次连接（刷新页面）应拿到同一份回放，并以终态立即关闭。
            replay = await asyncio.wait_for(read_stream(client, run_id), timeout=10)

    assert [event["seq"] for event in replay] == [event["seq"] for event in first]
    assert [event["type"] for event in replay] == [event["type"] for event in first]


async def test_stream_rejects_unknown_run(tmp_path) -> None:
    app = build_app(tmp_path, StreamingModel([{"deltas": ["x"]}]))
    api = await app.create_http_app()

    async with api.router.lifespan_context(api):
        transport = httpx.ASGITransport(app=api)
        async with httpx.AsyncClient(transport=transport, base_url="http://local") as client:
            assert (await client.get("/v1/runs/run_missing/stream")).status_code == 404
            assert (await client.get("/v1/sessions/conv_missing/messages")).status_code == 404


async def test_broker_replays_then_continues_without_duplicates() -> None:
    broker = RunEventBroker()
    broker.publish("run_x", {"type": "model.delta", "text": "a"})

    queue, replay, unsubscribe = broker.open("run_x")
    assert [event["seq"] for event in replay] == [1]

    broker.publish("run_x", {"type": "model.delta", "text": "b"})
    live = await asyncio.wait_for(queue.get(), timeout=1)
    assert live["seq"] == 2 and live["text"] == "b"

    unsubscribe()
    broker.publish("run_x", {"type": "model.delta", "text": "c"})
    assert queue.empty()
    assert broker.has_finished("run_x") is False

    broker.publish("run_x", {"type": "run.end", "status": "completed"})
    assert broker.has_finished("run_x") is True
