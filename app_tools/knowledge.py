from pydantic import BaseModel , ConfigDict
from harness.retrieval.retriever import RetrievalPipeline
from harness.retrieval.projector import RetrievalContextProjector
from harness.tools.factory import tool_from_pydantic

class SearchKnowledgeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str

def build_search_knowledge_tool( * , retrieval_pipeline , projector , tenant_id : str ,):
    def search_knowledge_base(query: str) -> str:
        results = retrieval_pipeline.search(
            query=query,
            candidate_k=12,
            final_k=5,
            where={
                "tenant_id": tenant_id,
            },
        )

        return projector.project(results)


    return tool_from_pydantic(
        name="search_knowledge_base",
        description="在当前租户知识库中检索与问题相关的证据；当回答依赖项目文档或内部知识时使用。",
        args_model=SearchKnowledgeArgs,
        handler=search_knowledge_base,
        timeout_seconds=10.0,
        max_retries=1,
        required_permissions=frozenset({
            "knowledge.search"
        }),
        side_effects=False,
        source="rag",
    )

# 已于0.6.0版本中弃用
# ----------------------------------------------------------------------------
# def build_search_knowledge_tool( * , pipeline : RetrievalPipeline , projector : RetrievalContextProjector , tenant_id : str) ->tool_from_pydantic:
#     """构建一个知识检索工具"""
#     def search_knowledge(query:str) -> str:
#         results = pipeline.search(
#             query=query,
#             candidate_k=15,
#             final_k=5,
#             tenant_id=tenant_id,
#             where={
#                 "tenant_id": tenant_id,
#             },
#         )
#         return projector.project(results)

#     return tool_from_pydantic(
#         name="search_knowledge_base",
#         description="Search for knowledge in the knowledge base",
#         args_model=SearchknowledgeArgs,
#         handler=search_knowledge,
#         timeout_seconds=10,
#         max_retries=1,
#         side_effects=False,
#     )






