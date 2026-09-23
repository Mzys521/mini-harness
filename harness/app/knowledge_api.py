# 文件：harness/app/knowledge_api.py
"""多 RAG 仓库的本地 HTTP 接口（供工作台前端使用）。

只注册路由，不注册中间件与异常处理器：错误映射（LookupError→404 / ValueError→400）
与同源保护中间件由 `install_desktop_routes` 统一提供，因此本模块必须在它之后安装。
RAG 未启用时端点仍然存在，但统一返回 503 与可执行的启用提示——比 404 更容易排查。
"""
from dataclasses import asdict

from fastapi import Body, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

_RAG_HINT = (
    "RAG 未启用：请安装 mini-harness[rag] 并在 harness.toml 打开 [rag].enabled。"
)


class KnowledgeRepositoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


def register_knowledge_routes(api, harness_app, runtime):
    def require_catalog():
        # 在调用时读取 runtime（而不是注册时捕获），因此运行时换入别的 Catalog、
        # 或在测试里注入替身都不需要重新建 app。
        catalog = runtime.knowledge
        if catalog is None:
            raise HTTPException(status_code=503, detail=_RAG_HINT)
        return catalog

    def require_repository(repository_id: str):
        active = require_catalog()
        if active.get_repository(repository_id) is None:
            raise LookupError(f"RAG 仓库不存在：{repository_id}")
        return active

    @api.get("/v1/knowledge/repositories")
    def get_repositories():
        active = require_catalog()
        return {
            "items": [
                asdict(item)
                for item in active.get_repositories()
            ]
        }

    @api.post("/v1/knowledge/repositories", status_code=201)
    def create_repository(body: KnowledgeRepositoryInput = Body(...)):
        active = require_catalog()
        return asdict(
            active.create_repository(
                body.name,
                owner_user_id=harness_app.config.app.local_user_id,
                description=body.description,
            )
        )

    @api.get("/v1/knowledge/repositories/{repository_id}")
    def get_repository(repository_id: str):
        active = require_repository(repository_id)
        return asdict(active.get_repository(repository_id))

    @api.delete("/v1/knowledge/repositories/{repository_id}")
    def delete_repository(repository_id: str):
        active = require_repository(repository_id)
        active.delete_repository(repository_id)
        return {"repository_id": repository_id, "deleted": True}

    @api.get("/v1/knowledge/repositories/{repository_id}/files")
    def get_files(repository_id: str):
        active = require_repository(repository_id)
        return {
            "repository_id": repository_id,
            "items": [
                asdict(item)
                for item in active.get_files(repository_id)
            ],
        }

    @api.post("/v1/knowledge/repositories/{repository_id}/files", status_code=201)
    async def create_file(repository_id: str, request: Request, filename: str):
        """原始请求体即文件内容，文件名走查询参数（与工作区知识库上传保持一致）。"""
        active = require_repository(repository_id)
        data = await request.body()
        return asdict(
            active.execute_ingest(
                repository_id,
                filename,
                data,
                uploaded_by=harness_app.config.app.local_user_id,
            )
        )
