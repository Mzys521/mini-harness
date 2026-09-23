# 文件：harness/retrieval/store.py
"""RAG 仓库元数据的持久化。

只做数据访问：不生成 id、不读时钟、不做校验，调用方给什么就存什么。
业务编排在 `harness/retrieval/catalog.py`。
"""
from harness.retrieval.models import (
    KnowledgeRepository,
    KnowledgeRepositoryFile,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_repositories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    embedding_model TEXT NOT NULL,
    collection_name TEXT NOT NULL UNIQUE,
    owner_user_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_repository_files (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL
        REFERENCES knowledge_repositories(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    embedding_model TEXT NOT NULL,
    uploaded_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (repository_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_repository_files_repository
    ON knowledge_repository_files(repository_id);
"""


class SQLiteKnowledgeRepositoryStore:
    """仓库与仓库文件的 SQLite 存储。

    表由本类自行创建（不进入核心 `persistence/schema.py`）：RAG 是可选能力，
    关闭 `[rag]` 时不应在核心里留下只属于它的表。
    """

    def __init__(self, database) -> None:
        self.database = database
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        connection = self.database.connect()
        try:
            connection.executescript(_SCHEMA)
            connection.commit()
        finally:
            connection.close()

    # ---- 仓库 ----

    def create_repository(self, repository: KnowledgeRepository) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO knowledge_repositories (
                    id, name, description, embedding_model,
                    collection_name, owner_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repository.id,
                    repository.name,
                    repository.description,
                    repository.embedding_model,
                    repository.collection_name,
                    repository.owner_user_id,
                    repository.created_at,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_repository(self, repository_id: str) -> KnowledgeRepository | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM knowledge_repositories WHERE id = ?",
                (repository_id,),
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else _to_repository(row)

    def get_repository_by_name(self, name: str) -> KnowledgeRepository | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM knowledge_repositories WHERE name = ?",
                (name,),
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else _to_repository(row)

    def get_repositories(self) -> list[KnowledgeRepository]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM knowledge_repositories ORDER BY created_at, id"
            ).fetchall()
        finally:
            connection.close()
        return [_to_repository(row) for row in rows]

    def delete_repository(self, repository_id: str) -> None:
        connection = self.database.connect()
        try:
            # 文件行由 ON DELETE CASCADE 一并清理（connect() 已开启 foreign_keys）。
            connection.execute(
                "DELETE FROM knowledge_repositories WHERE id = ?",
                (repository_id,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # ---- 仓库文件 ----

    def create_file(self, item: KnowledgeRepositoryFile) -> None:
        """同一仓库内同名文件视为覆盖：重新上传后登记的是最新一次分块结果。"""
        connection = self.database.connect()
        try:
            connection.execute(
                """
                INSERT INTO knowledge_repository_files (
                    id, repository_id, filename, stored_path, content_hash,
                    size_bytes, chunk_count, embedding_model, uploaded_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repository_id, filename) DO UPDATE SET
                    id = excluded.id,
                    stored_path = excluded.stored_path,
                    content_hash = excluded.content_hash,
                    size_bytes = excluded.size_bytes,
                    chunk_count = excluded.chunk_count,
                    embedding_model = excluded.embedding_model,
                    uploaded_by = excluded.uploaded_by,
                    created_at = excluded.created_at
                """,
                (
                    item.id,
                    item.repository_id,
                    item.filename,
                    item.stored_path,
                    getattr(item, "content_hash", ""),
                    item.size_bytes,
                    item.chunk_count,
                    item.embedding_model,
                    item.uploaded_by,
                    item.created_at,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_files(self, repository_id: str) -> list[KnowledgeRepositoryFile]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM knowledge_repository_files
                WHERE repository_id = ?
                ORDER BY created_at, filename
                """,
                (repository_id,),
            ).fetchall()
        finally:
            connection.close()
        return [_to_file(row) for row in rows]


def _to_repository(row) -> KnowledgeRepository:
    return KnowledgeRepository(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        embedding_model=row["embedding_model"],
        collection_name=row["collection_name"],
        owner_user_id=row["owner_user_id"],
        created_at=row["created_at"],
    )


def _to_file(row) -> KnowledgeRepositoryFile:
    return KnowledgeRepositoryFile(
        id=row["id"],
        repository_id=row["repository_id"],
        filename=row["filename"],
        stored_path=row["stored_path"],
        chunk_count=int(row["chunk_count"]),
        embedding_model=row["embedding_model"],
        size_bytes=int(row["size_bytes"]),
        uploaded_by=row["uploaded_by"],
        created_at=row["created_at"],
    )
