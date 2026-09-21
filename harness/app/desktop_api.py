"""HTTP adapters for the loopback-only personal workspace."""
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from harness.state.models import utc_now
from harness.streaming import TERMINAL_EVENT


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkspaceInput(Payload):
    path: str = Field(min_length=1)
    name: str = ""
    create: bool = False
    knowledge_path: str | None = None


class KnowledgePath(Payload):
    path: str = Field(min_length=1)


class SessionInput(Payload):
    workspace_id: str
    title: str = "新任务"


class SessionPatch(Payload):
    """会话重命名 / 归档；两个字段都可选，但不能同时为空。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None


class AgentInput(Payload):
    name: str = Field(min_length=1)
    instructions: str = Field(min_length=1)


class InstructionInput(Payload):
    text: str = Field(min_length=1, max_length=16000)


class ReplayInput(Payload):
    step_id: str | None = None


def _sse_frame(record: dict) -> str:
    """把一条事件编码成 SSE 帧；换行必须保持单行 JSON。"""
    return "data: " + json.dumps(record, ensure_ascii=False, default=str) + "\n\n"


def install_desktop_routes(api, harness_app, runtime):
    service = runtime.desktop

    @api.middleware("http")
    async def protect_local_api(request: Request, call_next):
        # A public web page must not operate the user's unauthenticated filesystem API.
        origin = request.headers.get("origin")
        if origin and urlparse(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse({"detail": "仅允许本地工作台访问"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "拒绝跨站请求"}, status_code=403)
        return await call_next(request)

    @api.exception_handler(LookupError)
    async def missing(request, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @api.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @api.exception_handler(OSError)
    async def filesystem_error(request, error):
        return JSONResponse({"detail": f"无法访问文件或目录：{error}"}, status_code=400)

    @api.get("/v1/directories")
    def directories(path: str | None = None):
        return service.browse(path)

    @api.get("/v1/workspaces")
    def workspaces():
        return {"items": service.rows("SELECT * FROM desktop_workspaces ORDER BY created_at DESC")}

    @api.post("/v1/workspaces", status_code=201)
    def add_workspace(body: WorkspaceInput):
        return service.add_workspace(**body.model_dump())

    @api.patch("/v1/workspaces/{workspace_id}/knowledge-path")
    def knowledge_path(workspace_id: str, body: KnowledgePath):
        service.workspace(workspace_id)
        path = Path(body.path).expanduser().resolve()
        if path.exists() and not path.is_dir():
            raise ValueError("知识库保存位置必须是目录")
        service.execute("UPDATE desktop_workspaces SET knowledge_path=? WHERE id=?", (str(path), workspace_id))
        return service.workspace(workspace_id)

    @api.delete("/v1/workspaces/{workspace_id}")
    def remove_workspace(workspace_id: str):
        service.workspace(workspace_id)
        if service.rows("SELECT id FROM desktop_sessions WHERE workspace_id=?", (workspace_id,)):
            raise HTTPException(409, "工作区已有会话，请保留目录关联以便回溯历史")
        service.execute("DELETE FROM desktop_documents WHERE workspace_id=?", (workspace_id,))
        service.execute("DELETE FROM desktop_workspaces WHERE id=?", (workspace_id,))
        return {"removed": True}

    @api.get("/v1/workspaces/{workspace_id}/files")
    def files(workspace_id: str, path: str = "."):
        return service.files(workspace_id, path)

    @api.get("/v1/workspaces/{workspace_id}/file")
    def file(workspace_id: str, path: str):
        return service.read_file(workspace_id, path)

    @api.get("/v1/workspaces/{workspace_id}/knowledge")
    def knowledge(workspace_id: str):
        service.workspace(workspace_id)
        return {"items": service.rows("SELECT id,name,source,stored_path,created_at FROM desktop_documents WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,))}

    @api.post("/v1/workspaces/{workspace_id}/knowledge/upload", status_code=201)
    async def upload(workspace_id: str, request: Request, filename: str):
        data = await request.body()
        return service.ingest(workspace_id, filename, data, "upload:" + filename)

    @api.post("/v1/workspaces/{workspace_id}/knowledge/import", status_code=201)
    def import_document(workspace_id: str, body: KnowledgePath):
        source = Path(body.path).expanduser().resolve()
        return service.ingest(workspace_id, source.name, source.read_bytes(), str(source))

    @api.delete("/v1/workspaces/{workspace_id}/knowledge/{document_id}")
    def remove_document(workspace_id: str, document_id: str):
        service.workspace(workspace_id)
        service.execute("DELETE FROM desktop_documents WHERE id=? AND workspace_id=?", (document_id, workspace_id))
        return {"removed": True, "files_retained": True}

    @api.get("/v1/sessions")
    def sessions(workspace_id: str, archived: bool = False):
        service.workspace(workspace_id)
        # 归档会话默认不返回，但列表里始终带上 archived 字段，前端可自行分组。
        return {"items": service.rows("SELECT * FROM desktop_sessions WHERE workspace_id=? AND archived=? ORDER BY created_at DESC", (workspace_id, 1 if archived else 0))}

    @api.post("/v1/sessions", status_code=201)
    def create_session(body: SessionInput):
        return service.new_session(body.workspace_id, body.title)

    @api.patch("/v1/sessions/{session_id}")
    def patch_session(session_id: str, body: SessionPatch):
        if body.title is None and body.archived is None:
            raise ValueError("请提供 title 或 archived")
        return service.update_session(session_id, title=body.title, archived=body.archived)

    @api.delete("/v1/sessions/{session_id}")
    def remove_session(session_id: str):
        active = service.session_active_runs(session_id)
        if active:
            raise HTTPException(409, "会话中还有正在执行的任务，请先停止或等待完成再删除")
        return service.delete_session(session_id)

    @api.get("/v1/sessions/{session_id}/messages")
    def messages(session_id: str):
        service.session(session_id)
        return {"items": service.rows("SELECT id,role,content,created_at FROM messages WHERE conversation_id=? ORDER BY created_at,rowid", (session_id,))}

    @api.get("/v1/agent")
    def agent():
        return service.agent()

    @api.put("/v1/agent")
    def save_agent(body: AgentInput):
        service.execute("INSERT INTO desktop_settings VALUES ('agent',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(body.model_dump(), ensure_ascii=False),))
        return service.agent()

    @api.get("/v1/runs")
    def list_runs(conversation_id: str | None = None):
        sql = "SELECT r.id FROM runs r JOIN conversations c ON c.id=r.conversation_id WHERE c.user_id=? AND c.tenant_id=?"
        args = [harness_app.config.app.local_user_id, harness_app.config.app.local_tenant_id]
        if conversation_id:
            sql += " AND r.conversation_id=?"
            args.append(conversation_id)
        rows = service.rows(sql + " ORDER BY r.created_at DESC", tuple(args))
        return {"items": [service.observed_run(runtime, row["id"]) for row in rows]}

    @api.get("/v1/runs/{run_id}/trace")
    def trace(run_id: str):
        return service.observed_run(runtime, run_id)

    @api.get("/v1/runs/{run_id}/stream")
    async def stream(run_id: str):
        """Server-Sent Events：模型增量、工具调用与运行状态实时下发。

        每个 SSE 帧都是一条 `data: {json}`，`type` 字段决定前端如何归并；
        缓冲会先整体回放，因此「提交任务」与「打开流」之间的竞态不会丢事件。
        """
        service.observed_run(runtime, run_id)    # 未知 Run 直接 404
        broker = runtime.events
        if broker is None:
            raise HTTPException(503, "当前运行时没有启用事件总线")

        queue, replay, unsubscribe = broker.open(run_id)

        async def frames():
            finished = False
            try:
                for record in replay:
                    yield _sse_frame(record)
                    finished = record.get("type") == TERMINAL_EVENT
                while not finished:
                    try:
                        record = await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        # 心跳注释帧：让浏览器与反代知道连接仍然健康。
                        yield ": keep-alive\n\n"
                        continue
                    yield _sse_frame(record)
                    finished = record.get("type") == TERMINAL_EVENT
            finally:
                unsubscribe()

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def active_record(run_id):
        service.observed_run(runtime, run_id)
        record = runtime.durable_store.get(run_id)
        if not record or record.status.value in {"completed", "cancelled", "failed"}:
            raise HTTPException(409, "运行已经结束，请创建新任务")
        return record

    @api.post("/v1/runs/{run_id}/pause", status_code=202)
    def pause(run_id: str):
        active_record(run_id)
        service.execute("INSERT INTO desktop_controls VALUES (?,1) ON CONFLICT(run_id) DO UPDATE SET paused=1", (run_id,))
        return {"status": "pause_requested", "detail": "将在当前模型或工具调用完成后暂停"}

    @api.post("/v1/runs/{run_id}/resume", status_code=202)
    def resume(run_id: str):
        record = active_record(run_id)
        service.execute("UPDATE desktop_controls SET paused=0 WHERE run_id=?", (run_id,))
        if record.execution.phase.value not in {"waiting_approval", "waiting_reconciliation"}:
            service.execute("UPDATE durable_runs SET status='pending',available_at=? WHERE run_id=? AND lease_owner IS NULL AND status='waiting'", (utc_now().isoformat(), run_id))
        return {"status": "resume_requested"}

    @api.post("/v1/runs/{run_id}/reject", status_code=202)
    def reject(run_id: str):
        record = active_record(run_id)
        if record.execution.phase.value != "waiting_approval":
            raise HTTPException(409, "此运行没有等待批准的操作")
        runtime.durable.cancel(run_id=run_id)
        service.execute("INSERT INTO events VALUES (?,?,NULL,?,?,?)", (f"evt_{uuid4().hex}", run_id, "run.rejected", json.dumps({"reason": "操作员拒绝执行"}, ensure_ascii=False), utc_now().isoformat()))
        return {"status": "cancel_requested"}

    @api.post("/v1/runs/{run_id}/instructions", status_code=202)
    def instruct(run_id: str, body: InstructionInput):
        active_record(run_id)
        service.execute("INSERT INTO desktop_instructions VALUES (?,?,?,?)", (f"instruction_{uuid4().hex}", run_id, body.text, utc_now().isoformat()))
        return {"status": "queued", "detail": "将在下一个执行边界加入模型上下文"}

    @api.post("/v1/runs/{run_id}/replay", status_code=202)
    def replay(run_id: str, body: ReplayInput):
        return service.replay(runtime, run_id, body.step_id)

    static = Path(__file__).resolve().parents[1] / "ui" / "static"
    if static.is_dir():
        @api.get("/", include_in_schema=False)
        def index():
            return FileResponse(static / "index.html")
        api.mount("/ui", StaticFiles(directory=static, html=True), name="ui")
