import math

def cosine_similarity(a : list[float], b : list[float]) -> float:

    if len(a) != len(b):
        raise ValueError("两个向量的维度必须相同")
    if not a : 
        raise ValueError("向量不能为空")
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)

    


