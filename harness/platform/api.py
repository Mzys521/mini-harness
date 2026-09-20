# 文件：harness/platform/api.py
import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from harness.platform.errors import PlatformError
from harness.platform.models import TenantStatus
from harness.ui import STATIC_DIRECTORY


class SubmitRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field(min_length=1, max_length=16_000)
    conversation_id: str | None = None


class TenantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    plan_id: str = Field(min_length=1, max_length=100)


class ApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(min_length=1, max_length=50)


class TenantStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TenantStatus


class TenantPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=1, max_length=100)


def create_app(commercial_runtime, *, start_background_workers: bool = True) -> FastAPI:
    platform = commercial_runtime.service
    api_key_header = APIKeyHeader(
        name="X-API-Key",
        scheme_name="HarnessApiKey",
        auto_error=False,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop_event = asyncio.Event()
        app.state.commercial_runtime = commercial_runtime

        if not start_background_workers:
            yield
            return

        async with asyncio.TaskGroup() as group:
            group.create_task(
                commercial_runtime.core.worker_pool.run_forever(
                    stop_event=stop_event
                ),
                name="durable-worker-pool",
            )
            group.create_task(
                commercial_runtime.metering.run_forever(
                    stop_event=stop_event
                ),
                name="usage-reconciler",
            )
            try:
                yield
            finally:
                stop_event.set()

    app = FastAPI(
        title="mini-harness Commercial Platform API",
        version="0.11.0",
        lifespan=lifespan,
    )

    app.mount("/ui", StaticFiles(directory=STATIC_DIRECTORY), name="workspace-assets")

    @app.get("/", include_in_schema=False)
    async def workspace():
        return FileResponse(STATIC_DIRECTORY / "index.html")

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(PlatformError)
    async def platform_error_handler(request: Request, exc: PlatformError):
        return JSONResponse(
            status_code=exc.status_code,
            media_type="application/problem+json",
            content={
                "type": f"urn:mini-harness:problem:{exc.code.lower()}",
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": str(request.url.path),
                "code": exc.code,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    def principal_dependency(raw_key: str | None = Depends(api_key_header)):
        return platform.authenticate(raw_key)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": "0.11.0"}

    @app.get("/v1/me")
    async def me(principal=Depends(principal_dependency)):
        return {
            "tenant_id": principal.tenant_id,
            "api_key_id": principal.api_key_id,
            "scopes": sorted(principal.scopes),
        }

    @app.post("/v1/runs", status_code=202)
    async def submit_run(body: SubmitRunRequest, principal=Depends(principal_dependency)):
        result = await platform.submit_run(
            principal=principal,
            user_input=body.input,
            conversation_id=body.conversation_id,
        )
        return asdict(result)

    @app.get("/v1/runs/{run_id}")
    async def get_run(run_id: str, principal=Depends(principal_dependency)):
        return asdict(platform.get_run(principal=principal, run_id=run_id))

    @app.post("/v1/runs/{run_id}/approve", status_code=202)
    async def approve_run(run_id: str, principal=Depends(principal_dependency)):
        platform.approve_run(principal=principal, run_id=run_id)
        return {"run_id": run_id, "status": "approval_recorded"}

    @app.post("/v1/runs/{run_id}/cancel", status_code=202)
    async def cancel_run(run_id: str, principal=Depends(principal_dependency)):
        platform.cancel_run(principal=principal, run_id=run_id)
        return {"run_id": run_id, "status": "cancel_requested"}

    @app.get("/v1/usage")
    async def usage(
        start: datetime,
        end: datetime,
        principal=Depends(principal_dependency),
    ):
        return asdict(
            platform.usage_summary(
                principal=principal,
                start=start,
                end=end,
            )
        )

    @app.get("/v1/billing/preview")
    async def billing_preview(
        start: datetime | None = None,
        end: datetime | None = None,
        principal=Depends(principal_dependency),
    ):
        return asdict(
            platform.billing_preview(
                principal=principal,
                start=start,
                end=end,
            )
        )

    @app.get("/v1/admin/plans")
    async def admin_list_plans(principal=Depends(principal_dependency)):
        return [
            asdict(item)
            for item in platform.admin_list_plans(principal=principal)
        ]

    @app.get("/v1/admin/tenants")
    async def admin_list_tenants(principal=Depends(principal_dependency)):
        return [
            asdict(item)
            for item in platform.admin_list_tenants(principal=principal)
        ]

    @app.post("/v1/admin/tenants", status_code=201)
    async def admin_create_tenant(
        body: TenantCreateRequest,
        principal=Depends(principal_dependency),
    ):
        tenant = platform.admin_create_tenant(
            principal=principal,
            tenant_id=body.tenant_id,
            name=body.name,
            plan_id=body.plan_id,
        )
        return asdict(tenant)

    @app.post("/v1/admin/tenants/{tenant_id}/api-keys", status_code=201)
    async def admin_create_api_key(
        tenant_id: str,
        body: ApiKeyCreateRequest,
        principal=Depends(principal_dependency),
    ):
        issued = platform.admin_create_api_key(
            principal=principal,
            tenant_id=tenant_id,
            name=body.name,
            scopes=frozenset(body.scopes),
        )
        # 明文 key 只在创建响应中出现一次。
        return {
            "api_key_id": issued.record.id,
            "tenant_id": issued.record.tenant_id,
            "secret": issued.secret,
            "scopes": sorted(issued.record.scopes),
        }

    @app.post("/v1/admin/tenants/{tenant_id}/plan")
    async def admin_set_plan(
        tenant_id: str,
        body: TenantPlanRequest,
        principal=Depends(principal_dependency),
    ):
        platform.admin_set_tenant_plan(
            principal=principal,
            tenant_id=tenant_id,
            plan_id=body.plan_id,
        )
        return {"tenant_id": tenant_id, "plan_id": body.plan_id}

    @app.post("/v1/admin/tenants/{tenant_id}/status")
    async def admin_set_status(
        tenant_id: str,
        body: TenantStatusRequest,
        principal=Depends(principal_dependency),
    ):
        platform.admin_set_tenant_status(
            principal=principal,
            tenant_id=tenant_id,
            status=body.status,
        )
        return {"tenant_id": tenant_id, "status": body.status.value}

    return app
