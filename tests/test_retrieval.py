from harness.retrieval.ingestion import IngestionService
from harness.retrieval.memory_store import InMemoryVectorStore
from harness.retrieval.models import Document
from harness.retrieval.retriever import DenseRetriever
from harness.retrieval.chunkers import CharacterChunker
from tests.test_fakes import FakeEmbeddingProvider

def test_retrieval_respects_tenant_filter() -> None:
    embedding = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    ingestion = IngestionService(
        chunker=CharacterChunker(chunk_size=1000, overlap=100),
        embedding_provider=embedding,
        vector_store=store,
    )
    ingestion.ingest(Document(id="doc_a", text="context context context", metadata={"tenant_id": "tenant_a"}))
    ingestion.ingest(Document(id="doc_b", text="context context context", metadata={"tenant_id": "tenant_b"}))

    retriever = DenseRetriever(embedding_provider=embedding, vector_store=store)
    results = retriever.retrieve("context", top_k=10, where={"tenant_id": "tenant_a"})

    assert results
    assert all(item.chunk.metadata["tenant_id"] == "tenant_a" for item in results)



def test_delete_by_document_removes_chunks() -> None:
    embedding = FakeEmbeddingProvider()
    store = InMemoryVectorStore()
    ingestion = IngestionService(chunker=CharacterChunker(chunk_size=1000, overlap=100), embedding_provider=embedding, vector_store=store)
    ingestion.ingest(Document(id="doc_1", text="tool tool tool", metadata={"tenant_id": "tenant_a"}))

    store.delete_by_document("doc_1")
    results = DenseRetriever(embedding_provider=embedding, vector_store=store).retrieve("tool", top_k=10)

    assert results == []