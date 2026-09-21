# 文件：harness/app/features.py
from pydantic import BaseModel, ConfigDict

from harness.tools.factory import tool_from_pydantic


class SearchKnowledgeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


def build_rag_tool(*, name: str, retrieval_pipeline, projector):
    """Core 内置 RAG Tool；不再依赖示例目录 app_tools。"""
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

    return tool_from_pydantic(
        name=name,
        description="在当前租户知识库中检索与问题相关的证据。",
        args_model=SearchKnowledgeArgs,
        handler=search_knowledge_base,
        timeout_seconds=10.0,
        max_retries=1,
        required_permissions=frozenset({"knowledge.search"}),
        side_effect=False,
        source="rag",
        inject_context=True,
    )
