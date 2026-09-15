import pytest

class FakeEmbeddingProvider:

    def embed_documents(self , texts : list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> list[float]:
        return [
            float(text.lower().count("context")) , 
            float(text.lower().count("tool")) , 
            float(text.lower().count("checkpoint")),
            float(len(text) % 97)
        ]


@pytest.mark.parametrize("text", ["context tool checkpoint"])
def test_fake_embedding_provider(text):
    fake_embedding_provider = FakeEmbeddingProvider()
    assert fake_embedding_provider.embed_query(text) == [1.0, 1.0, 1.0, float(len(text) % 97)]



