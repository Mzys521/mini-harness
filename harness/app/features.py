# 文件：harness/app/features.py
from pydantic import BaseModel, ConfigDict, Field

from harness.tools.factory import tool_from_pydantic


class SearchKnowledgeArgs(BaseModel):
    """单集合（旧）检索：schema 保持不变，避免影响既有调用方。"""

    model_config = ConfigDict(extra="forbid")
    query: str


class SearchKnowledgeRepositoryArgs(BaseModel):
    """多仓库检索：必须指定仓库，仓库之间互不可见。"""

    model_config = ConfigDict(extra="forbid")
    query: str
    repository_id: str = Field(min_length=1)


class WriteKnowledgeFileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    content: str = Field(min_length=1)


def build_rag_tool(*, name: str, retrieval_pipeline, projector, catalog=None):
    """Core 内置 RAG Tool；不再依赖示例目录 app_tools。

    参数 catalog: 传入 KnowledgeRepositoryCatalog 时，工具额外支持按 `repository_id`
    在指定仓库内检索；不传时行为与 schema 都与旧版完全一致。
    """
    if catalog is None:
        def search_knowledge_base(query: str, *, context) -> str:
            if not context.tenant_id:
                raise PermissionError("tenant_id is required")
            results = retrieval_pipeline.search(
                query,
                candidate_k=12,
                final_k=5,
                where={"tenant_id": context.tenant_id},
            )
            return projector.project(results)

        args_model = SearchKnowledgeArgs
        description = "在当前租户知识库中检索与问题相关的证据。"
    else:
        def search_knowledge_base(
            query: str,
            *,
            context,
            repository_id: str,
        ) -> str:
            results = catalog.execute_search(
                repository_id,
                query,
                candidate_k=12,
                final_k=5,
            )
            return projector.project(results)

        args_model = SearchKnowledgeRepositoryArgs
        description = "在指定的 RAG 仓库中检索与问题相关的证据。"

    return tool_from_pydantic(
        name=name,
        description=description,
        args_model=args_model,
        handler=search_knowledge_base,
        timeout_seconds=10.0,
        max_retries=1,
        required_permissions=frozenset({"knowledge.search"}),
        side_effect=False,
        source="rag",
        inject_context=True,
    )


def create_rag_write_tool(*, name: str, catalog):
    """Agent 写入 RAG 仓库的唯一入口：声明副作用与审批，批准后才落盘并建索引。

    授权模型复用 Phase 9 的确定性 Tool Policy + 持久 ApprovalStore：
    调用会停在 `APPROVAL_REQUIRED`，由用户在前端批准 / 拒绝，跨进程可恢复。
    工具本身不做权限判断，`required_permissions={"rag.write"}` 由执行器校验。
    """
    def write_knowledge_file(
        repository_id: str,
        filename: str,
        content: str,
        *,
        context,
    ) -> dict:
        item = catalog.execute_ingest(
            repository_id,
            filename,
            content,
            uploaded_by=context.user_id or "",
        )
        return {
            "repository_id": item.repository_id,
            "filename": item.filename,
            "chunks": item.chunk_count,
            "embedding_model": item.embedding_model,
            "size_bytes": item.size_bytes,
            "created_at": item.created_at,
        }

    return tool_from_pydantic(
        name=name,
        description=(
            "把一份文本写入指定 RAG 仓库并建立向量索引。"
            "该操作会修改知识库内容，需要用户批准后才会执行。"
        ),
        args_model=WriteKnowledgeFileArgs,
        handler=write_knowledge_file,
        timeout_seconds=30.0,
        max_retries=0,
        required_permissions=frozenset({"rag.write"}),
        side_effect=True,
        requires_approval=True,
        source="rag",
        inject_context=True,
    )
