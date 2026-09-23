# 文件：harness/retrieval/models.py
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    """一份原始知识文档。"""
    id: str
    text: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(frozen=True)
class Chunk:
    """从文档切出的最小检索单元。"""
    id: str
    document_id: str
    text: str
    index: int
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(frozen=True)
class RetrievalResult:
    """统一检索结果，不暴露具体向量数据库对象。"""
    chunk: Chunk
    score: float
    rank: int

@dataclass(frozen=True)
class RetrievalRequest:
    """一次完整知识检索请求。"""
    query: str
    tenant_id: str
    candidate_k: int = 20
    final_k: int = 5
    filters: dict[str, Any] = field(
        default_factory=dict
    )

@dataclass(frozen=True)
class KnowledgeRepository:
    """一个相互隔离的 RAG 仓库。

    隔离由「一个仓库一个向量集合」实现：`collection_name` 只属于本仓库，
    因此删除仓库就是丢弃整份索引，不需要按 metadata 反选删除。
    """
    id: str
    name: str
    embedding_model: str
    collection_name: str
    owner_user_id: str
    description: str = ""
    created_at: str = ""

@dataclass(frozen=True)
class KnowledgeRepositoryFile:
    """仓库里一份已索引的文件，同时是 chunk 的来源记录。"""
    id: str
    repository_id: str
    filename: str
    stored_path: str
    chunk_count: int
    embedding_model: str
    size_bytes: int = 0
    uploaded_by: str = ""
    created_at: str = ""

# 每个 chunk 必须带齐的元数据：上传文件名、向量化模型名、日期、归属仓库。
# 契约写在 ingest() 里，缺失直接报错而不是静默写入残缺索引。
REQUIRED_CHUNK_METADATA = (
    "filename",
    "repository_id",
    "embedding_model",
    "uploaded_at",
)
