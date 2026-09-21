# 文件：harness/app/server.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict

from pydantic import BaseModel, ConfigDict, Field

from harness import __version__
from harness.app.errors import FeatureDependencyError, UnsafeServerConfigurationError


class SubmitRunRequest(BaseModel):
    """请求体模型必须在模块级定义。

    FastAPI 需要能解析注解；如果在函数内延迟定义、又用字符串注解，
    pydantic 只会拿到 ForwardRef，路由注册时就会报 not fully defined。
    pydantic 属于 Core 依赖，模块级导入不会把 FastAPI 变成硬依赖。
    """

    model_config = ConfigDict(extra="forbid")
    input: str = Field(min_length=1, max_length=16_000)
    conversation_id: str | None = None
    workspace_id: str | None = None


def _server_imports():
    try:
        from fastapi import Body, FastAPI
    except ImportError as exc:
        raise FeatureDependencyError(
            "server",
            'pip install "mini-harness[server]"',
        ) from exc
    return FastAPI, Body


def validate_local_bind(host: str, *, allow_unsafe_public_no_auth: bool) -> None:
    loopback = {"127.0.0.1", "localhost", "::1"}
    if host not in loopback and not allow_unsafe_public_no_auth:
        raise UnsafeServerConfigurationError(
            "Local API 没有 Authentication，只允许绑定 loopback。"
            "若你明确知道风险，可设置 server.allow_unsafe_public_no_auth=true；"
            "公网部署更推荐 server.mode='platform'。"
        )


def create_http_app(harness_app, runtime):
    mode = harness_app.config.server.mode
    if mode == "platform":
        if runtime.platform is None:
            raise RuntimeError(
                "server.mode='platform' 时必须设置 [platform].enabled=true。"
            )
        try:
            from harness.platform.api import create_app as create_platform_app
        except ImportError as exc:
            raise FeatureDependencyError(
                "server",
                'pip install "mini-harness[server]"',
            ) from exc
        return create_platform_app(runtime.platform)

    if mode != "local":
        raise ValueError(f"unknown server mode: {mode}")

    validate_local_bind(
        harness_app.config.server.host,
        allow_unsafe_public_no_auth=(
            harness_app.config.server.allow_unsafe_public_no_auth
        ),
    )
    return _create_local_app(harness_app, runtime)


def _create_local_app(harness_app, runtime):
    FastAPI, Body = _server_imports()

    @asynccontextmanager
    async def lifespan(app):
        stop_event = asyncio.Event()
        app.state.runtime = runtime
        async with asyncio.TaskGroup() as group:
            group.create_task(
                runtime.worker_pool.run_forever(stop_event=stop_event),
                name="durable-worker-pool",
            )
            try:
                yield
            finally:
                stop_event.set()

    api = FastAPI(
        title=f"{harness_app.config.app.name} API",
        version=__version__,
        description=(
            "Local-first API。默认无认证且仅允许 loopback；"
            "公网多租户部署请启用 Platform Extension。"
        ),
        lifespan=lifespan,
    )

    @api.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": __version__, "mode": "local"}

    @api.post("/v1/runs", status_code=202)
    async def submit_run(body: SubmitRunRequest = Body(...)):
        workspace_id = body.workspace_id
        if body.conversation_id:
            sessions = runtime.desktop.rows("SELECT * FROM desktop_sessions WHERE id=?", (body.conversation_id,))
            if sessions:
                bound = sessions[0]["workspace_id"]
                if workspace_id and workspace_id != bound:
                    raise ValueError("会话已绑定另一个工作区，请新建会话")
                workspace_id = bound
        context = runtime.desktop.agent()["instructions"]
        # 工作区目录在这里解析一次并写进 ToolContext：工具层因此不必回头问数据库。
        workspace_path = None
        knowledge_path = None
        if workspace_id:
            workspace = runtime.desktop.workspace(workspace_id)
            workspace_path = workspace["path"]
            knowledge_path = workspace["knowledge_path"]
            context += f"\n当前工作区：{workspace_path}。使用 workspace 工具读取、修改文件和运行测试。知识资料可用 workspace_knowledge_search 检索。"
        result = await runtime.durable.submit(
            user_input=body.input, conversation_id=body.conversation_id,
            user_id=harness_app.config.app.local_user_id,
            tenant_id=harness_app.config.app.local_tenant_id,
            permissions=harness_app.local_permissions(),
            workspace_id=workspace_id, workspace_path=workspace_path, knowledge_path=knowledge_path,
            external_context=context,
        )
        return asdict(result)

    @api.get("/v1/runs/{run_id}")
    async def get_run(run_id: str):
        return asdict(await harness_app.get_run(run_id))

    @api.post("/v1/runs/{run_id}/approve", status_code=202)
    async def approve_run(run_id: str):
        await harness_app.approve(run_id)
        return {"run_id": run_id, "status": "approval_recorded"}

    @api.post("/v1/runs/{run_id}/cancel", status_code=202)
    async def cancel_run(run_id: str):
        await harness_app.cancel(run_id)
        return {"run_id": run_id, "status": "cancel_requested"}

    from harness.app.desktop_api import install_desktop_routes
    install_desktop_routes(api, harness_app, runtime)
    return api
