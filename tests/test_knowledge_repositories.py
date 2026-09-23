"""多 RAG 仓库：隔离、chunk 元数据、授权写入与文件清单。

这些用例**不需要 [rag] extra**：向量库通过 `vector_store_factory` 注入内存替身，
因此仓库编排逻辑在只装内核的环境里也能跑（CI 目前正是这种情况）。
"""
import asyncio
from dataclasses import replace
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from harness import HarnessApp, HarnessConfig
from harness.app.features import create_rag_write_tool
from harness.models import ToolCall
from harness.persistence.database import Database
from harness.retrieval.catalog import KnowledgeRepositoryCatalog
from harness.retrieval.chunkers import CharacterChunker
from harness.retrieval.models import (
    REQUIRED_CHUNK_METADATA,
    RetrievalResult,
)
from harness.retrieval.store import SQLiteKnowledgeRepositoryStore
from harness.security import (
    DefaultToolPolicy,
    InMemoryApprovalStore,
    InMemoryRunBudgetStore,
    SecurityAction,
)
from harness.security.config import SecurityConfig
from harness.tools.definition import ToolContext
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry


class FakeEmbeddingProvider:
    """确定性向量：只依赖文本本身，足以验证写入与检索链路。"""

    model = "fake-embedding-v1"

    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)

    @staticmethod
    def _vector(text):
        return [
            float(len(text)),
            float(sum(map(ord, text)) % 97),
            1.0,
        ]


class FakeVectorStore:
    """内存向量库替身：按 collection_name 隔离，用于断言仓库之间互不可见。"""

    collections: ClassVar[dict] = {}

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self.collection = self.collections.setdefault(collection_name, {})

    def upsert(self, *, chunks, embeddings):
        for chunk, embedding in zip(chunks, embeddings):
            self.collection[chunk.id] = (chunk, embedding)

    def search(self, *, query_embedding, top_k=5, where=None):
        results = []
        for chunk, embedding in self.collection.values():
            if where and any(
                chunk.metadata.get(key) != value
                for key, value in where.items()
            ):
                continue
            distance = sum(
                (left - right) ** 2
                for left, right in zip(embedding, query_embedding)
            ) ** 0.5
            results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=1.0 / (1.0 + distance),
                    rank=0,
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def delete_by_document(self, document_id):
        for key, (chunk, _) in list(self.collection.items()):
            if chunk.document_id == document_id:
                del self.collection[key]

    def delete_all(self):
        self.collection.clear()


class StubModel:
    async def generate(self, **kwargs):
        raise AssertionError("本用例不调用模型")


@pytest.fixture
def catalog(tmp_path):
    FakeVectorStore.collections.clear()
    database = Database(str(tmp_path / "rag.db"))
    database.initialize()
    return KnowledgeRepositoryCatalog(
        store=SQLiteKnowledgeRepositoryStore(database),
        embedding_provider=FakeEmbeddingProvider(),
        chunker=CharacterChunker(chunk_size=40, overlap=0),
        vector_store_factory=lambda repository: FakeVectorStore(
            repository.collection_name
        ),
        storage_path=str(tmp_path / "rag_files"),
    )


def build_client(tmp_path, catalog):
    """真实 Local HTTP app + 注入的 Catalog 替身（路由在调用时读取 runtime）。"""
    base = HarnessConfig()
    config = replace(
        base,
        app=replace(base.app, database_path=str(tmp_path / "app.db")),
    )
    app = HarnessApp(config, model_provider=StubModel())
    api = asyncio.run(app.create_http_app())
    app.runtime.knowledge = catalog
    return TestClient(api)


# ---- 仓库隔离与文件清单 ----


def test_repositories_are_isolated_and_files_are_listed(catalog):
    first = catalog.create_repository("产品手册")
    second = catalog.create_repository("运维手册")

    assert first.collection_name != second.collection_name
    assert first.collection_name == f"repo_{first.id}"

    item = catalog.execute_ingest(
        first.id,
        "intro.md",
        "Harness 是一个可扩展的 Agent 运行内核。",
    )

    assert item.filename == "intro.md"
    assert item.chunk_count >= 1
    assert item.embedding_model == "fake-embedding-v1"
    assert item.created_at

    assert [entry.filename for entry in catalog.get_files(first.id)] == ["intro.md"]
    # 第二个仓库看不到第一个仓库的文件与向量。
    assert catalog.get_files(second.id) == []
    assert catalog.execute_search(second.id, "Harness") == []
    assert catalog.execute_search(first.id, "Harness") != []


def test_chunks_record_filename_model_date_and_repository(catalog):
    repository = catalog.create_repository("规范")
    catalog.execute_ingest(repository.id, "spec.md", "写测试，再改实现。")

    chunks = [
        chunk
        for chunk, _ in FakeVectorStore(
            repository.collection_name
        ).collection.values()
    ]
    assert chunks

    for chunk in chunks:
        for key in REQUIRED_CHUNK_METADATA:
            assert chunk.metadata.get(key), f"chunk 缺少 {key}"
        assert chunk.metadata["filename"] == "spec.md"
        assert chunk.metadata["repository_id"] == repository.id
        assert chunk.metadata["embedding_model"] == "fake-embedding-v1"
        assert chunk.metadata["uploaded_at"]


def test_reuploading_the_same_filename_replaces_old_chunks(catalog):
    repository = catalog.create_repository("日志")
    catalog.execute_ingest(repository.id, "note.md", "第一版内容" * 20)
    catalog.execute_ingest(repository.id, "note.md", "第二版" * 5)

    files = catalog.get_files(repository.id)
    assert len(files) == 1
    assert files[0].filename == "note.md"

    texts = [
        chunk.text
        for chunk, _ in FakeVectorStore(repository.collection_name).collection.values()
    ]
    assert texts
    assert all("第一版" not in text for text in texts)


def test_delete_repository_drops_vectors_and_rows(catalog):
    repository = catalog.create_repository("临时")
    catalog.execute_ingest(repository.id, "a.md", "内容")

    assert catalog.delete_repository(repository.id) is True
    assert catalog.get_repository(repository.id) is None
    assert catalog.get_files(repository.id) == []
    assert FakeVectorStore(repository.collection_name).collection == {}
    # 重复删除返回 False，不抛异常。
    assert catalog.delete_repository(repository.id) is False


def test_duplicate_name_and_unknown_repository_are_rejected(catalog):
    catalog.create_repository("唯一")
    with pytest.raises(ValueError):
        catalog.create_repository("唯一")
    with pytest.raises(ValueError):
        catalog.create_repository("   ")
    with pytest.raises(LookupError):
        catalog.execute_ingest("kr_missing", "a.md", "内容")
    with pytest.raises(LookupError):
        catalog.execute_search("kr_missing", "查询")


def test_filename_is_reduced_to_a_basename(catalog, tmp_path):
    repository = catalog.create_repository("越界")

    item = catalog.execute_ingest(
        repository.id,
        "../../etc/passwd",
        "不该写到仓库目录之外",
    )
    assert item.filename == "passwd"
    assert (tmp_path / "rag_files" / repository.id / "passwd").exists()

    with pytest.raises(ValueError):
        catalog.execute_ingest(repository.id, "..", "内容")


# ---- 授权写入 ----


def test_write_tool_requires_approval_and_ingests(catalog):
    tool = create_rag_write_tool(name="rag_write_file", catalog=catalog)

    assert tool.side_effect is True
    assert tool.requires_approval is True
    assert tool.required_permissions == frozenset({"rag.write"})

    # 审批闸门来自确定性的 Tool Policy，而不是工具自己。
    decision = DefaultToolPolicy(
        config=SecurityConfig(),
        approval_store=InMemoryApprovalStore(),
        budget_store=InMemoryRunBudgetStore(),
    ).authorize(
        tool=tool,
        call=ToolCall(
            call_id="call_1",
            name="rag_write_file",
            arguments={"repository_id": "kr_1", "filename": "a.md", "content": "x"},
        ),
        context=ToolContext(run_id="run_1"),
    )
    assert decision.action is SecurityAction.APPROVAL_REQUIRED

    repository = catalog.create_repository("授权")

    # 第一道闸门：Run 必须被授予 rag.write 权限，否则执行器直接拒绝。
    denied = asyncio.run(
        ToolExecutor(_registry_with(tool)).execute(
            ToolCall(
                call_id="call_2",
                name="rag_write_file",
                arguments={
                    "repository_id": repository.id,
                    "filename": "approved.md",
                    "content": "批准之后才写入。",
                },
            ),
            ToolContext(run_id="run_1", user_id="local_user"),
        )
    )
    assert denied.status.value == "permission_denied"
    assert catalog.get_files(repository.id) == []

    # 第二道闸门：拿到权限后仍需用户批准，批准后同一调用才真正落盘建索引。
    result = asyncio.run(
        ToolExecutor(_registry_with(tool)).execute(
            ToolCall(
                call_id="call_3",
                name="rag_write_file",
                arguments={
                    "repository_id": repository.id,
                    "filename": "approved.md",
                    "content": "批准之后才写入。",
                },
            ),
            ToolContext(
                run_id="run_1",
                user_id="local_user",
                permissions=frozenset({"rag.write"}),
            ),
        )
    )

    assert result.ok is True
    assert result.data["chunks"] >= 1
    assert [entry.filename for entry in catalog.get_files(repository.id)] == [
        "approved.md"
    ]


def _registry_with(tool):
    registry = ToolRegistry()
    registry.register(tool)
    return registry


# ---- HTTP 接口 ----


def test_knowledge_api_creates_lists_and_deletes_repositories(tmp_path, catalog):
    with build_client(tmp_path, catalog) as client:
        assert client.get("/v1/knowledge/repositories").json()["items"] == []

        created = client.post(
            "/v1/knowledge/repositories",
            json={"name": "接口仓库", "description": "来自前端"},
        )
        assert created.status_code == 201
        repository = created.json()
        assert repository["name"] == "接口仓库"
        assert repository["embedding_model"] == "fake-embedding-v1"

        uploaded = client.post(
            f"/v1/knowledge/repositories/{repository['id']}/files",
            params={"filename": "readme.md"},
            content="通过接口写入的内容。".encode(),
        )
        assert uploaded.status_code == 201
        assert uploaded.json()["filename"] == "readme.md"

        listed = client.get(
            f"/v1/knowledge/repositories/{repository['id']}/files"
        )
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert [entry["filename"] for entry in items] == ["readme.md"]
        assert items[0]["chunk_count"] >= 1
        assert items[0]["embedding_model"] == "fake-embedding-v1"
        assert items[0]["created_at"]

        # 同名重复创建 → 400
        assert (
            client.post(
                "/v1/knowledge/repositories",
                json={"name": "接口仓库"},
            ).status_code
            == 400
        )
        # 未知仓库上传 → 404
        assert (
            client.post(
                "/v1/knowledge/repositories/kr_missing/files",
                params={"filename": "a.md"},
                content=b"x",
            ).status_code
            == 404
        )

        assert (
            client.delete(
                f"/v1/knowledge/repositories/{repository['id']}"
            ).status_code
            == 200
        )
        assert client.get("/v1/knowledge/repositories").json()["items"] == []


def test_knowledge_api_reports_disabled_rag(tmp_path):
    """RAG 未启用时给可执行的启用提示，而不是让前端猜 404。"""
    base = HarnessConfig()
    config = replace(
        base,
        app=replace(base.app, database_path=str(tmp_path / "app.db")),
    )
    app = HarnessApp(config, model_provider=StubModel())
    api = asyncio.run(app.create_http_app())

    with TestClient(api) as client:
        response = client.get("/v1/knowledge/repositories")
        assert response.status_code == 503
        assert "[rag]" in response.json()["detail"]
