from collections.abc import Sequence

import httpx

_BASE_URL = "https://openrouter.ai/api/v1"


class EmbeddingError(RuntimeError):
    pass


class OpenRouterEmbedder:
    """Embeddings via POST {base_url}/embeddings (OpenAI-compatible request/response shape).

    Verified only against a simulated transport; not yet exercised against the real API.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        dimensions: int = 1536,
        batch_size: int = 64,
        base_url: str = _BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._url = f"{base_url}/embeddings"
        self._client = client or httpx.Client(timeout=30.0)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            out.extend(self._embed_batch(list(texts[start : start + self._batch_size])))
        return out

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        try:
            response = self._client.post(
                self._url,
                headers=self._headers,
                json={"model": self._model, "input": batch},
            )
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"embedding request failed: {exc}") from exc
        if response.status_code != 200:
            raise EmbeddingError(f"embedding request returned HTTP {response.status_code}")
        data = sorted(response.json().get("data", []), key=lambda d: d["index"])
        vectors = [d["embedding"] for d in data]
        if len(vectors) != len(batch):
            raise EmbeddingError(f"expected {len(batch)} embeddings, got {len(vectors)}")
        for v in vectors:
            if len(v) != self._dimensions:
                raise EmbeddingError(f"expected {self._dimensions} dimensions, got {len(v)}")
        return vectors
