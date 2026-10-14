import json

import httpx
import pytest

from copilot.adapters.outbound.llm.openrouter_embedder import EmbeddingError, OpenRouterEmbedder


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _embedder(handler, **kw) -> OpenRouterEmbedder:
    return OpenRouterEmbedder("sk-test", "m/x", dimensions=3, client=_client(handler), **kw)


def test_sends_model_input_and_auth_and_sorts_by_index():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                ]
            },
        )

    out = _embedder(handler).embed(["a", "b"])
    assert out == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert seen["url"] == "https://openrouter.ai/api/v1/embeddings"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"] == {"model": "m/x", "input": ["a", "b"]}


def test_splits_into_batches():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["input"]
        calls.append(len(inputs))
        return httpx.Response(
            200, json={"data": [{"index": i, "embedding": [0.0] * 3} for i in range(len(inputs))]}
        )

    assert len(_embedder(handler, batch_size=2).embed(["a", "b", "c"])) == 3
    assert calls == [2, 1]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={}),
        httpx.Response(200, json={"data": []}),
        httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]}),
    ],
    ids=["http-error", "missing-vectors", "wrong-dimensions"],
)
def test_errors_are_explicit(response):
    with pytest.raises(EmbeddingError):
        _embedder(lambda request: response).embed(["a"])


def test_network_failure_becomes_embedding_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(EmbeddingError, match="failed"):
        _embedder(handler).embed(["a"])
