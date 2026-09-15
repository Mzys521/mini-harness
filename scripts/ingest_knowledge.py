from harness.retrieval.ids import stable_id
from harness.retrieval.loaders import load_text_file
from harness.retrieval.chunkers import CharacterChunker


source = "E:\\项目\\ascll3D\\CMakeLists.txt"
document = load_text_file(
    source,
    document_id=stable_id("doc", f"tenant_001:{source}:v1"),
    metadata={"tenant_id": "tenant_001", "version": "v1", "document_type": "learning_note"},
)

chunks = CharacterChunker(chunk_size=10, overlap=2).split(document)

print("文档长度：", len(document.text))
print("文本块数量：", len(chunks))
for chunk in chunks:
    print("\n--- 文本块", chunk.index, "---")
    print(chunk.text[:10])