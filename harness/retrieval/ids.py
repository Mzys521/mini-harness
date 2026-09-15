import hashlib

def stable_id(prefix: str , value : str) ->str:
    """相同输入得到相同标识符，方便去重和更新"""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"

def content_hash(text: str) -> str:
    """计算正文哈希，用于判断文档是否真的发生变化"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()






