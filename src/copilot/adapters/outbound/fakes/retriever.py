from copilot.domain.procedures import RetrievedChunk


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.calls: list[tuple[str, int, str | None]] = []

    def search(self, query: str, k: int, event_type: str | None = None) -> list[RetrievedChunk]:
        self.calls.append((query, k, event_type))
        return self._chunks[:k]
