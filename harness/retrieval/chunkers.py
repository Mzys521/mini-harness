from harness.retrieval.models import Document , Chunk
from harness.retrieval.ids import stable_id
from harness.state.models import Step

class CharacterChunker:
    def __init__(self , chunk_size: int = 1000 , overlap: int = 120) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于0")
        
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须满足 0 <= overlap < chunk_size")
        
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self , document: Document) -> list[Chunk]:
        text = document.text.strip()
        if not text:
            return []
        chunks : list[Chunk] = []
        start , index = 0 , 0 
        step = self.chunk_size - self.overlap

        while start < len(text):
            end = min(start + self.chunk_size , len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = stable_id("chunk" , f"{document.id}:{index}:{chunk_text}")
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document.id,
                        text=chunk_text,
                        index=index,
                        metadata = {
                            **document.metadata,
                            "chunk_index": index,
                        }
                    )
                )
                index += 1
            if end >= len(text):
                break
            start += step
        
        return chunks

    




