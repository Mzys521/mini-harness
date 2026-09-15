from harness.retrieval.models import Document
from harness.retrieval.embeddings import EmbeddingProvider
from harness.retrieval.chunkers import CharacterChunker


class IngestionService:
    def __init__(self , * , chunker : CharacterChunker , embedding_provider : EmbeddingProvider , vector_store  ) -> None:

        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def ingest(self , document: Document) -> int:
        chunks = self.chunker.split(document)
        if not chunks: 
            return 0
        
        embedding = self.embedding_provider.embed_documents([chunk.text for chunk in chunks])
        self.vector_store.upsert(chunks = chunks , embeddings = embedding)
        return len(chunks)
    

