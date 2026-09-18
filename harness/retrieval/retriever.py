from harness.retrieval.models import RetrievalResult
from harness.retrieval.embeddings import EmbeddingProvider
from time import perf_counter

class DenseRetriever:
    def __init__(self , * , embedding_provider , vector_store) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def retrieve(self , query: str , * , top_k : int = 5 , where: dict | None = None) -> list[RetrievalResult]:
        if not query.strip():
            return []
        query_embedding = self.embedding_provider.embed_query(query)
        return self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where
        )

class NoOpReranker:
    def rerank(self , * , query: str , candidates: list , top_k: int) -> list[RetrievalResult]:
        return candidates[:top_k]

class RetrievalPipeline:
    def __init__(self , * , retriever, reranker = None, observability, metrics) -> None:
        self.retriever = retriever
        self.reranker = reranker or NoOpReranker()
        self.observability = observability
        self.metrics = metrics
    
    def search(self, query: str, *, candidate_k: int = 12, final_k: int = 5, where: dict | None = None):
        started = perf_counter()

        with self.observability.span(
            "retrieval.search",
            {
                "retrieval.candidate_k": candidate_k,
                "retrieval.final_k": final_k,
            },
        ) as span:
            candidates = self.retriever.retrieve(query, top_k=candidate_k, where=where)
            results = self.reranker.rerank(query=query, candidates=candidates, top_k=final_k)
            
            span.set_attribute("retrieval.candidate_count", len(candidates))
            span.set_attribute("retrieval.result_count", len(results))
            
            self.metrics.retrieval_duration.record(perf_counter() - started)
            self.metrics.retrieval_result_count.record(len(results))
            return results








