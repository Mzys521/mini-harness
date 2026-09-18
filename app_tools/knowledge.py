from pydantic import (
    BaseModel,
    ConfigDict,
)

from harness.tools.factory import (
    tool_from_pydantic,
)

class SearchKnowledgeArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )
    query: str

def build_search_knowledge_tool(
    *,
    retrieval_pipeline,
    projector,
):
    def search_knowledge_base(
        query: str,
        *,
        context,
    ) -> str:
        # tenant_id 来自 ToolContext，不允许 LLM 自己提交。
        if not context.tenant_id:
            raise PermissionError(
                "tenant_id is required"
            )

        results = retrieval_pipeline.search(
            query,
            candidate_k=12,
            final_k=5,
            where={
                "tenant_id": context.tenant_id
            },
        )

        return projector.project(
            results
        )

    return tool_from_pydantic(
        name="search_knowledge_base",
        description=(
            "在当前租户知识库中检索与问题相关的证据；"
            "当回答依赖项目文档或内部知识时使用。"
        ),
        args_model=SearchKnowledgeArgs,
        handler=search_knowledge_base,
        timeout_seconds=10.0,
        max_retries=1,
        required_permissions=frozenset({
            "knowledge.search"
        }),
        side_effect=False,
        source="rag",
        inject_context=True,
    )