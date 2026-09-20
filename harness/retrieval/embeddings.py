# 文件：harness/retrieval/embeddings.py
import os
from typing import Protocol

from openai import OpenAI

# 未配置 DASHSCOPE_BASE_URL 时的回退地址（DashScope OpenAI 兼容模式）。
_DASHSCOPE_COMPATIBLE_BASE_URL = (
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

class EmbeddingProvider(Protocol):
    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        ...

class OpenAIEmbeddingProvider:
    """OpenAI Embeddings Adapter；Retrieval Core 仍只依赖 EmbeddingProvider。"""

    def __init__(
        self,
        *,
        model: str = "text-embedding-3-small",
        batch_size: int = 64,
    ) -> None:
        self.client = OpenAI()
        self.model = model
        self.batch_size = batch_size

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []

        for start in range(
            0,
            len(texts),
            self.batch_size,
        ):
            batch = texts[
                start:
                start + self.batch_size
            ]
            response = (
                self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
            )
            ordered = sorted(
                response.data,
                key=lambda item: item.index,
            )
            vectors.extend(
                item.embedding
                for item in ordered
            )

        return vectors

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        if not text.strip():
            raise ValueError(
                "查询文本不能为空"
            )

        response = (
            self.client.embeddings.create(
                model=self.model,
                input=text,
            )
        )
        return response.data[
            0
        ].embedding

class QwenEmbeddingProvider:
    """通义千问（DashScope OpenAI 兼容模式）Embedding Adapter。

    与 OpenAIEmbeddingProvider 同构：Retrieval Core 只依赖 EmbeddingProvider，
    因此两者可以互换，不影响 DenseRetriever / RetrievalPipeline。
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        batch_size: int = 10,
    ) -> None:
        """初始化。

        参数 model: 模型名（默认 DASHSCOPE_MODEL，回退 text-embedding-v3）
        参数 api_key: API 密钥（默认 DASHSCOPE_API_KEY）
        参数 base_url: 接口地址（默认 DASHSCOPE_BASE_URL，回退 DashScope 兼容模式地址）
        参数 batch_size: 单批文本数（默认 10，DashScope 单次请求上限）
        """
        self.client = OpenAI(
            api_key=(
                api_key
                or os.getenv("DASHSCOPE_API_KEY")
            ),
            base_url=(
                base_url
                or os.getenv("DASHSCOPE_BASE_URL")
                or _DASHSCOPE_COMPATIBLE_BASE_URL
            ),
        )
        self.model = (
            model
            or os.getenv(
                "DASHSCOPE_MODEL",
                "text-embedding-v3",
            )
        )
        self.batch_size = batch_size

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []

        for start in range(
            0,
            len(texts),
            self.batch_size,
        ):
            batch = texts[
                start:
                start + self.batch_size
            ]
            response = (
                self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
            )
            ordered = sorted(
                response.data,
                key=lambda item: item.index,
            )
            vectors.extend(
                item.embedding
                for item in ordered
            )

        return vectors

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        if not text.strip():
            raise ValueError(
                "查询文本不能为空"
            )

        response = (
            self.client.embeddings.create(
                model=self.model,
                input=text,
            )
        )
        return response.data[
            0
        ].embedding
