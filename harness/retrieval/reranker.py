from typing import Protocol
from harness.retrieval.models import RetrievalResult

class Reranker(Protocol):
    def rerank(self, *, query: str, candidates: list[RetrievalResult], top_k: int) -> list[RetrievalResult]: ...

class NoOpReranker(Reranker):
    def rerank(self, *, query: str, candidates: list[RetrievalResult], top_k: int) -> list[RetrievalResult]:
        return candidates[:top_k]
