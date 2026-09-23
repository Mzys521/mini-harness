# 文件：harness/retrieval/catalog.py
"""多 RAG 仓库的编排层。

依赖方向（单向）：catalog → store / vector_store / ingestion / retriever。
catalog 不被 retrieval 的其他模块反向依赖，也不 import `harness.app`。

向量库通过 `vector_store_factory` 注入而不是自己 import chromadb：这样
① `[rag]` 之外也能导入本模块并测试仓库编排逻辑；② 向量后端可以整体替换。
"""
from pathlib import Path

from harness.retrieval.chunkers import CharacterChunker
from harness.retrieval.embeddings import EmbeddingProvider
from harness.retrieval.ids import stable_id
from harness.retrieval.ingestion import IngestionService
from harness.retrieval.models import (
    Document,
    KnowledgeRepository,
    KnowledgeRepositoryFile,
)
from harness.retrieval.retriever import (
    DenseRetriever,
    RetrievalPipeline,
)
from harness.retrieval.store import (
    SQLiteKnowledgeRepositoryStore,
)
from harness.state.ids import new_id
from harness.state.models import utc_now


class KnowledgeRepositoryCatalog:
    """RAG 仓库的创建 / 查询 / 删除，以及仓库内的文件摄取与检索。

    隔离模型：一个仓库一个向量集合（`collection_name` 由仓库 id 派生），
    因此「删除仓库」= 丢弃整份索引，不需要按 metadata 反选删除，也不会误伤别的仓库。
    """

    def __init__(
        self,
        *,
        store: SQLiteKnowledgeRepositoryStore,
        embedding_provider: EmbeddingProvider,
        chunker: CharacterChunker,
        vector_store_factory,
        storage_path: str,
        observability=None,
        metrics=None,
    ) -> None:
        self.store = store
        self.embedding_provider = embedding_provider
        self.chunker = chunker
        self.vector_store_factory = vector_store_factory
        self.storage_path = Path(storage_path)
        self.observability = observability
        self.metrics = metrics
        # 向量化模型名以 provider 的实际生效模型为准，仓库与 chunk 都记录它。
        self.embedding_model = (
            getattr(embedding_provider, "model", None)
            or "unknown"
        )

    # ---- 仓库 ----

    def create_repository(
        self,
        name: str,
        *,
        owner_user_id: str = "",
        description: str = "",
    ) -> KnowledgeRepository:
        normalized = name.strip()
        if not normalized:
            raise ValueError("仓库名不能为空。")
        if self.store.get_repository_by_name(normalized) is not None:
            raise ValueError(f"仓库已存在：{normalized}")

        repository_id = new_id("kr")
        repository = KnowledgeRepository(
            id=repository_id,
            name=normalized,
            description=description,
            embedding_model=self.embedding_model,
            collection_name=f"repo_{repository_id}",
            owner_user_id=owner_user_id,
            created_at=utc_now().isoformat(),
        )
        self.store.create_repository(repository)
        return repository

    def get_repository(
        self,
        repository_id: str,
    ) -> KnowledgeRepository | None:
        return self.store.get_repository(repository_id)

    def get_repositories(self) -> list[KnowledgeRepository]:
        return self.store.get_repositories()

    def delete_repository(self, repository_id: str) -> bool:
        """删除仓库：先丢弃向量集合，再删元数据。返回是否真的删掉了一个仓库。"""
        repository = self.store.get_repository(repository_id)
        if repository is None:
            return False
        self.vector_store_factory(repository).delete_all()
        self.store.delete_repository(repository_id)
        return True

    # ---- 文件 ----

    def execute_ingest(
        self,
        repository_id: str,
        filename: str,
        content: str | bytes,
        *,
        uploaded_by: str = "",
    ) -> KnowledgeRepositoryFile:
        """把一份文件写入仓库并建立索引。同名文件重新上传视为覆盖。"""
        repository = self.store.get_repository(repository_id)
        if repository is None:
            raise LookupError(f"RAG 仓库不存在：{repository_id}")

        # 只取文件名本身：仓库目录不接收任何路径成分，避免越界写入。
        safe_name = Path(filename).name.strip()
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError(f"非法文件名：{filename}")

        text = (
            content.decode("utf-8", errors="replace")
            if isinstance(content, (bytes, bytearray))
            else content
        )
        size_bytes = (
            len(content)
            if isinstance(content, (bytes, bytearray))
            else len(text.encode("utf-8"))
        )
        created_at = utc_now().isoformat()
        # document_id 只由「仓库 + 文件名」决定：重新上传会命中同一批 chunk id，
        # 配合下面的 delete_by_document 把上一次的内容彻底换掉。
        document_id = stable_id("doc", f"{repository_id}:{safe_name}")

        vector_store = self.vector_store_factory(repository)
        vector_store.delete_by_document(document_id)

        chunk_count = IngestionService(
            chunker=self.chunker,
            embedding_provider=self.embedding_provider,
            vector_store=vector_store,
        ).ingest(
            Document(
                id=document_id,
                text=text,
                metadata={
                    "filename": safe_name,
                    "repository_id": repository_id,
                    "uploaded_at": created_at,
                },
            )
        )

        stored_path = self._write_file(repository_id, safe_name, content)
        item = KnowledgeRepositoryFile(
            id=stable_id("krf", f"{repository_id}:{safe_name}"),
            repository_id=repository_id,
            filename=safe_name,
            stored_path=str(stored_path),
            chunk_count=chunk_count,
            embedding_model=self.embedding_model,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
            created_at=created_at,
        )
        self.store.create_file(item)
        return item

    def get_files(
        self,
        repository_id: str,
    ) -> list[KnowledgeRepositoryFile]:
        return self.store.get_files(repository_id)

    # ---- 检索 ----

    def execute_search(
        self,
        repository_id: str,
        query: str,
        *,
        candidate_k: int = 12,
        final_k: int = 5,
    ):
        """在指定仓库内检索。仓库之间不共享集合，因此不需要 tenant 过滤兜底。"""
        repository = self.store.get_repository(repository_id)
        if repository is None:
            raise LookupError(f"RAG 仓库不存在：{repository_id}")

        pipeline = RetrievalPipeline(
            retriever=DenseRetriever(
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store_factory(repository),
            ),
            observability=self.observability,
            metrics=self.metrics,
        )
        return pipeline.search(
            query,
            candidate_k=candidate_k,
            final_k=final_k,
        )

    # ---- 内部 ----

    def _write_file(
        self,
        repository_id: str,
        filename: str,
        content: str | bytes,
    ) -> Path:
        directory = self.storage_path / repository_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / filename
        if isinstance(content, (bytes, bytearray)):
            target.write_bytes(bytes(content))
        else:
            target.write_text(content, encoding="utf-8")
        return target
