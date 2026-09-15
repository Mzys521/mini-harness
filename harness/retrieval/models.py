from dataclasses import dataclass , field
from typing import Any

@dataclass(frozen=True)
class Document:
    """一份原始知识文档"""
    id: str
    text: str
    metadata: dict[str , Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """从文档当中切割出的最小检索单元"""
    id : str
    document_id: str
    text: str
    index: int
    metadata: dict[str , Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RetrievalResult:
    """统一检索结果"""
    chunk: Chunk
    score: float
    rank: int

@dataclass(frozen=True)
class RetrievalResults:
    """一次完整的知识检索请求"""
    query : str
    tenant_id: str
    candidate_k : int = 20
    final_k : int = 5
    filter: dict[str , Any] = field(default_factory=dict)


