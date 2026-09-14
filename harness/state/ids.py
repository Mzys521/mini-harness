from uuid import uuid4

def new_id(prefix: str) -> str:
    """生成带前缀的唯一ID。
    参数 prefix: 前缀(如 cp、run)
    返回: 形如 "prefix-<32位hex>" 的字符串
    """
    return f"{prefix}-{uuid4().hex}"
