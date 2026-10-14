from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from copilot.domain.models import Event, Suggestion
from copilot.domain.procedures import Procedure, RetrievedChunk


class EmbedderPort(Protocol):
    @property
    def model(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class ProcedureStore(Protocol):
    def ingestion_state(self) -> dict[str, tuple[str, str | None]]:
        """code -> (content_hash, embedding_model) of what is already stored."""
        ...

    def replace_procedure(
        self,
        procedure: Procedure,
        embeddings: list[list[float]] | None,
        embedding_model: str | None,
    ) -> None: ...


class RetrieverPort(Protocol):
    def search(self, query: str, k: int, event_type: str | None = None) -> list[RetrievedChunk]:
        """Chunks of valid procedures, best first. Procedures whose `applies_to` contains
        `event_type` are boosted and are candidates even when the text does not match."""
        ...


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str


class LLMPort(Protocol):
    def complete(self, system: str, user: str) -> LLMResponse: ...


class AuditPort(Protocol):
    def append(self, event_id: str, kind: str, payload: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    kind: str
    at: datetime
    payload: dict[str, Any]
    hash: str


class AuditReader(Protocol):
    def trail(self, event_id: str) -> tuple[list[AuditEntry], bool]:
        """Entries in order and whether the hash chain is intact."""
        ...


class EventRepository(Protocol):
    def save(self, event: Event) -> None: ...

    def get(self, event_id: str) -> Event | None: ...


class SuggestionRepository(Protocol):
    def save(self, suggestion: Suggestion) -> None: ...

    def get(self, suggestion_id: str, *, for_update: bool = False) -> Suggestion | None: ...

    def record_decision(
        self,
        suggestion_id: str,
        outcome: str,
        justification: str | None,
        decided_by: str,
        new_status: str,
    ) -> None: ...
