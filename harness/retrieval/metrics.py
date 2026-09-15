

def recall_at_k(result , relevant_document_ids : set[str] , k : int) -> float :
    """正确文档中，有多少个再前K个中"""
    if not relevant_document_ids:
        return 1.0

    retrieved = {item.chunk.document_id for item in result[:k]}
    hits = len(retrieved & relevant_document_ids)

    return hits / len(relevant_document_ids)



















