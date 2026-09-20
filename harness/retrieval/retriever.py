# 文件：harness/retrieval/retriever.py
from time import perf_counter

class DenseRetriever:
    def __init__(
        self,
        *,
        embedding_provider,
        vector_store,
    ) -> None:
        self.embedding_provider = (
            embedding_provider
        )
        self.vector_store = (
            vector_store
        )

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 8,
        where: dict | None = None,
    ):
        if not query.strip():
            return []

        embedding = (
            self.embedding_provider.embed_query(
                query
            )
        )
        return self.vector_store.search(
            query_embedding=embedding,
            top_k=top_k,
            where=where,
        )

class NoOpReranker:
    def rerank(
        self,
        *,
        query: str,
        candidates: list,
        top_k: int,
    ):
        del query
        return candidates[:top_k]

class RetrievalPipeline:
    def __init__(
        self,
        *,
        retriever,
        reranker=None,
        observability=None,
        metrics=None,
    ) -> None:
        self.retriever = retriever
        self.reranker = (
            reranker
            or NoOpReranker()
        )
        self.observability = observability
        self.metrics = metrics

    def search(
        self,
        query: str,
        *,
        candidate_k: int = 12,
        final_k: int = 5,
        where: dict | None = None,
    ):
        started = perf_counter()

        span_context = (
            self.observability.span(
                "retrieval.search",
                {
                    "retrieval.candidate_k": candidate_k,
                    "retrieval.final_k": final_k,
                },
            )
            if self.observability is not None
            else _NullSpanContext()
        )

        with span_context as span:
            candidates = (
                self.retriever.retrieve(
                    query,
                    top_k=candidate_k,
                    where=where,
                )
            )
            results = (
                self.reranker.rerank(
                    query=query,
                    candidates=candidates,
                    top_k=final_k,
                )
            )

            span.set_attribute(
                "retrieval.candidate_count",
                len(candidates),
            )
            span.set_attribute(
                "retrieval.result_count",
                len(results),
            )

            if self.metrics is not None:
                self.metrics.retrieval_duration.record(
                    perf_counter() - started
                )
                self.metrics.retrieval_result_count.record(
                    len(results)
                )

            return results

class _NullSpan:
    def set_attribute(
        self,
        key,
        value,
    ) -> None:
        return None

class _NullSpanContext:
    def __enter__(self):
        return _NullSpan()

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False
