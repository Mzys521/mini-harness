from dataclasses import dataclass
from typing import Any

from harness.retrieval.models import Chunk , RetrievalResult
from harness.retrieval.simlarity import cosine_similarity
from harness.retrieval.vector_store import VectorStore

@dataclass
class _StoredVector(VectorStore):
    chunk: Chunk
    embedding : list[float]

class InMemoryVectorStore:
    def __init__(self) -> None:
        self._items: dict[str , _StoredVector] ={}

    def upsert(self , * , chunks: list[Chunk] , embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与embeddings 的长度必须相同")

        for chunk, embedding in zip(chunks , embeddings):
            self._items[chunk.id] = _StoredVector(chunk, embedding)

    def search(self , * , query_embedding: list[float] , top_k : int = 5 , where: dict[str, Any] | None = None) -> list[RetrievalResult]: 
        scored : list[tuple[float , Chunk]] = []
        
        for item in self._items.values():

            if  where and not self._matches(item.chunk.metadata, where):
                continue
            score = cosine_similarity(query_embedding, item.embedding)
            scored.append((score, item.chunk))
        
        scored.sort(key=lambda x: x[0], reverse=True) # 根据分数排序

        return [RetrievalResult(chunk = chunk , score = score , rank = rank) for rank, (score, chunk) in enumerate(scored[:top_k], start=1)]

    def delete_by_document(self , document_id : str) -> None:
        ids = [chunk_id for chunk_id , item in self._items.items() if item.chunk.document_id == document_id]

        for chunk_id in ids:
            del self._items[chunk_id]
    
    @staticmethod
    def _matches(metadata: dict , where : dict) -> bool:
        return all(metadata.get(key) == value for key, value in where.items())


























































