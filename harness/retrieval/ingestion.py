# 文件：harness/retrieval/ingestion.py
from dataclasses import replace

from harness.retrieval.chunkers import CharacterChunker
from harness.retrieval.embeddings import EmbeddingProvider
from harness.retrieval.models import (
    REQUIRED_CHUNK_METADATA,
    Document,
)


class IngestionService:
    """把一份文档切分、向量化并写入向量库。

    职责边界：本类只负责「补齐 chunk 元数据 → 嵌入 → upsert」。
    仓库归属、文件清单、日期由调用方（KnowledgeRepositoryCatalog）在构造
    Document 时给出；向量化模型名只有本类知道（来自 embedding provider），
    因此由它补齐。
    """

    def __init__(self , * , chunker : CharacterChunker , embedding_provider : EmbeddingProvider , vector_store  ) -> None:

        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def ingest(self , document: Document) -> int:
        chunks = self.chunker.split(document)
        if not chunks: 
            return 0

        # 向量化模型名取自 provider 的实际生效模型，而不是配置里的期望值。
        model_name = (
            getattr(self.embedding_provider, "model", None)
            or "unknown"
        )
        stamped = [
            replace(
                chunk,
                metadata={
                    **chunk.metadata,
                    "embedding_model": model_name,
                },
            )
            for chunk in chunks
        ]

        # 硬契约：四个必填字段缺一不可，宁可在写入前失败，也不要留下查不出出处的索引。
        missing = [
            name
            for name in REQUIRED_CHUNK_METADATA
            if not stamped[0].metadata.get(name)
        ]
        if missing:
            raise ValueError(
                "chunk 元数据缺少必填字段："
                + ", ".join(missing)
            )

        embedding = self.embedding_provider.embed_documents([chunk.text for chunk in stamped])
        self.vector_store.upsert(chunks = stamped , embeddings = embedding)
        return len(stamped)
