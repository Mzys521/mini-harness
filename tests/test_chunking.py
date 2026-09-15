from harness.retrieval.chunkers import CharacterChunker
from harness.retrieval.models import Document

def test_chunker_creates_multiple_chunks() -> None:
    document = Document(id="doc_1", text="A" * 3000)
    chunks = CharacterChunker(chunk_size=1000, overlap=100).split(document)
    assert len(chunks) > 1
    assert all(chunk.document_id == "doc_1" for chunk in chunks)

def test_chunk_ids_are_stable() -> None:
    document = Document(id="doc_1", text="hello " * 500)
    chunker = CharacterChunker(chunk_size=500, overlap=50)
    first = chunker.split(document)
    second = chunker.split(document)
    assert [x.id for x in first] == [x.id for x in second]