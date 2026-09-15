from pydantic import BaseModel , ConfigDict
from harness.tools.definition import Tool
from harness.retrieval.retriever import RetrievalPipeline
from harness.retrieval.projector import RetrievalContextProjector


class SearchknowledgeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


def build_search_knowledge_tool( * , pipeline : RetrievalPipeline , projector : RetrievalContextProjector , tenant_id : str) ->Tool:
    """构建一个知识检索工具"""
    def search_knowledge(query:str) -> str:
        results = pipeline.search(
            query=query,
            candidate_k=15,
            final_k=5,
            tenant_id=tenant_id,
            where={
                "tenant_id": tenant_id,
            },
        )
        return projector.project(results)

    return Tool(
        name="search_knowledge_base",
        description="Search for knowledge in the knowledge base",
        args_model=SearchknowledgeArgs,
        handler=search_knowledge,
        timeout_seconds=10,
        max_retries=1,
        side_effects=False,
    )






