from typing import Any


class InMemoryAudit:
    """Plain list; the hash-chained PostgreSQL implementation comes with the API (M3)."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str, dict[str, Any]]] = []

    def append(self, event_id: str, kind: str, payload: dict[str, Any]) -> None:
        self.entries.append((event_id, kind, payload))

    def kinds(self) -> list[str]:
        return [kind for _, kind, _ in self.entries]
