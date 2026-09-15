import os
from typing import Protocol
from openai import OpenAI

class EmbeddingProvider(Protocol):
    """检索核心只依赖这个接口，不绑定具体提供商"""
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """使用 OpenAI 向量嵌入接口实现 EmbeddingProvider。"""
    def __init__(self, *, model: str = "text-embedding-3-small", batch_size: int = 64) -> None:
        self.client = OpenAI()
        self.model = model
        self.batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            # 按 index 排序，确保输出顺序与输入文本顺序一致。
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("查询文本不能为空")
        response = self.client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding


class QwenEmbeddingProvider(EmbeddingProvider):
    """使用通义千问(DashScope OpenAI 兼容模式)向量嵌入接口实现 EmbeddingProvider。"""
    def __init__(self, *, model: str | None = None, api_key: str | None = None, base_url: str | None = None, batch_size: int = 10,) -> None:
        """初始化。
        参数 model: 模型名(默认读环境变量 DASHSCOPE_MODEL，回退 text-embedding-v3)
        参数 api_key: API 密钥(默认读环境变量 DASHSCOPE_API_KEY)
        参数 base_url: 接口地址(默认读环境变量 DASHSCOPE_BASE_URL，回退 DashScope 兼容模式地址)
        参数 batch_size: 单批文本数(默认 10，DashScope 单次请求上限)
        """
        self.client = OpenAI(
            api_key=api_key or os.getenv("DASHSCOPE_API_KEY"),
            base_url=base_url or os.getenv("DASHSCOPE_BASE_URL"),
        )
        self.model = model or os.getenv("DASHSCOPE_MODEL", "text-embedding-v3")
        self.batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文档。
        参数 texts: 待向量化的文本列表
        返回: 与输入顺序一致的向量列表
        """
        print("Embedding base_url:", self.client.base_url)
        print("Embedding model:", self.model)

        if not texts:
            return []
        vectors: list[list[float]] = []

        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            # 按 index 排序，确保输出顺序与输入文本顺序一致。
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """向量化单条查询。
        参数 text: 查询文本
        返回: 查询向量
        """
        if not text.strip():
            raise ValueError("查询文本不能为空")
        response = self.client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding