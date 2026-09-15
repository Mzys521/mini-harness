from pathlib import Path
from harness.retrieval.models import Document

def load_text_file(path: str , * , document_id : str , metadata: dict | None = None) -> Document:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    merged = {
        "source" : str(file_path),
        "filename" : file_path.name,
    }

    if metadata :
        merged.update(metadata)
    return Document(
        id=document_id,
        text=text,
        metadata=merged,
    )
