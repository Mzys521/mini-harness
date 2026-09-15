from typing import Protocol
from harness.retrieval.models import  Chunk , RetrievalResult

class VectorStore(Protocol):
    def upsert(self, * , chunks: list[Chunk], embeddings : list[list[float]]) -> None: ...
    def search(self, * , query_embedding: list[float] , top_k : int = 5 , where: dict | None = None) -> list[RetrievalResult]: ...    
    def delete_by_document(self , document_id : str) -> None: ...    



