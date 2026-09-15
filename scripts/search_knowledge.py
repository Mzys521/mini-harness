from harness.retrieval.chroma_store import ChromaVectorStore
from harness.retrieval.chunkers import CharacterChunker
from harness.retrieval.loaders import load_text_file
from harness.retrieval.ids import stable_id
from harness.retrieval.ingestion import IngestionService
from harness.retrieval.embeddings import OpenAIEmbeddingProvider , QwenEmbeddingProvider
from harness.retrieval.memory_store import InMemoryVectorStore
from harness.retrieval.retriever import DenseRetriever

from dotenv import load_dotenv

load_dotenv()

source = "E:\\自学文档\\harness\\Agent_Harness_从0到商业化_02_Production_Tool_Runtime.md"
document = load_text_file(source, document_id=stable_id("doc", f"tenant_001:{source}:v1"), metadata={"tenant_id": "tenant_001", "version": "v1"})
embedding_provider = QwenEmbeddingProvider()

vector_store = ChromaVectorStore(
    path="data/chroma",
    collection_name="harness_knowledge_v1"
)

vector_store = InMemoryVectorStore()
ingestion = IngestionService(chunker=CharacterChunker(chunk_size=1000, overlap=120), embedding_provider=embedding_provider, vector_store=vector_store)
ingestion.ingest(document)

retriever = DenseRetriever(embedding_provider=embedding_provider, vector_store=vector_store)
results = retriever.retrieve("工具调用如何实现？", top_k=5, where={"tenant_id": "tenant_001"})

for item in results:
    print(f"\n排名={item.rank} 分数={item.score:.4f}")
    print("来源：", item.chunk.metadata.get("source"))
    print(item.chunk.text[:300])










