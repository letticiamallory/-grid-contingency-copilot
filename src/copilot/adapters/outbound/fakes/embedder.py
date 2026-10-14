import hashlib
import math
import struct
from collections.abc import Sequence


class FakeEmbedder:
    """Deterministic pseudo-embeddings for tests: no semantic meaning, same text -> same vector."""

    model = "fake-embedder"

    def __init__(self, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self._dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend(v / 2**31 - 1 for v in struct.unpack("8I", digest))
            counter += 1
        values = values[: self._dimensions]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]
