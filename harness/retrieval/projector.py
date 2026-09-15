from harness.retrieval.models import RetrievalResult

class RetrievalContextProjector:
    """检索结果的投影器"""
    def project(self , result:  list[RetrievalResult]) ->str:
        sections : list[str] = []
        for item in result:
            source =  item.chunk.metadata.get("source" , "unknown") 
            section = item.chunk.metadata.get("section" , "")   
            sections.append(
                f"[证据 {item.rank} | 来源={source} | 章节={section} | 检索分数={item.score:.4f}]\n{item.chunk.text}"
            )
        return "\n\n".join(sections)
        