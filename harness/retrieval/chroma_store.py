import logging

import chromadb

from harness.retrieval.models import Chunk, RetrievalResult
from harness.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)

class ChromaVectorStore(VectorStore):
    def __init__(self , * , path : str , collection_name : str , client = None) -> None:
        # client 可复用：多个 RAG 仓库各占一个集合，但共用同一个 PersistentClient，
        # 避免为每个仓库重复打开同一份本地索引。
        self.path = path
        self.collection_name = collection_name
        self.client = client or chromadb.PersistentClient(path = path)
        self.collection = self._open_collection()

    def _open_collection(self):
        return self.client.get_or_create_collection(
            name = self.collection_name,
            embedding_function=None,
            configuration={
                "hnsw" : {
                    "space": "cosine"
                }
            }
        )

    def upsert(self , * ,chunks : list[Chunk] , embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 的长度不一致")
        
        if not chunks:
            return 
        
        self.collection.upsert(
            ids = [chunk.id for chunk in chunks],
            documents= [chunk.text for chunk in chunks],
            metadatas=[
                {
                    **chunk.metadata , 
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.index,
                } for chunk in chunks
            ],
            embeddings = embeddings,
        )

    def search(self , * , query_embedding : list[float] , top_k : int = 5 , where : dict | None = None) -> list[RetrievalResult]:
        raw = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=[
                "documents",
                "metadatas",
                "distances",
            ]
        )

        results: list[RetrievalResult] = []

        for rank , (chunk_id , text , metadata , distance ) in enumerate(
            zip(raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]) , start = 1 
        ):
            metadata = metadata or {}
            chunk = Chunk(
                id = chunk_id,
                document_id = str(metadata.get("document_id")),
                text=text or "",
                index = int(metadata.get("chunk_index" , 0)),
                metadata=metadata,
            )

            results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=1.0 - float(distance),
                    rank=rank,
                )
            )

        return results
    
    def delete_by_document(self , document_id : str) -> None:
        self.collection.delete(where={
            "document_id": document_id
        })

    def delete_all(self) -> None:
        """丢弃整个集合（删除 RAG 仓库），随后重新打开一个空集合，保证幂等。"""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as exc:  # noqa: BLE001 - 集合不存在时删除是幂等操作
            logger.debug(
                "向量集合 %s 删除时不存在或已被删除：%s",
                self.collection_name,
                exc,
            )
        self.collection = self._open_collection()


















