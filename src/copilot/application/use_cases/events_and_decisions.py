import uuid
from datetime import datetime
from typing import Any

from copilot.application.ports import (
    AuditEntry,
    AuditPort,
    AuditReader,
    EventRepository,
    SuggestionRepository,
)
from copilot.application.use_cases.generate_suggestion import GenerateSuggestion
from copilot.domain import rules
from copilot.domain.errors import EventNotFound, SuggestionNotFound
from copilot.domain.models import Event, Suggestion


class RegisterEvent:
    def __init__(self, events: EventRepository, audit: AuditPort) -> None:
        self._events = events
        self._audit = audit

    def execute(
        self,
        *,
        type: str,
        element: str,
        occurred_at: datetime,
        attributes: dict[str, Any],
        reported_by: str,
    ) -> Event:
        event = Event(str(uuid.uuid4()), type, element, occurred_at, attributes, reported_by)
        self._events.save(event)
        self._audit.append(
            event.id,
            "EVENT_RECEIVED",
            {"type": type, "element": element, "reported_by": reported_by},
        )
        return event


class SuggestForEvent:
    def __init__(
        self,
        events: EventRepository,
        generator: GenerateSuggestion,
        suggestions: SuggestionRepository,
    ) -> None:
        self._events = events
        self._generator = generator
        self._suggestions = suggestions

    def execute(self, event_id: str) -> Suggestion:
        event = self._events.get(event_id)
        if event is None:
            raise EventNotFound(f"evento {event_id} nao encontrado")
        suggestion = self._generator.execute(event)
        self._suggestions.save(suggestion)
        return suggestion


class RecordDecision:
    def __init__(self, suggestions: SuggestionRepository, audit: AuditPort) -> None:
        self._suggestions = suggestions
        self._audit = audit

    def execute(
        self, suggestion_id: str, outcome: str, justification: str | None, decided_by: str
    ) -> Suggestion:
        current = self._suggestions.get(suggestion_id, for_update=True)
        if current is None:
            raise SuggestionNotFound(f"sugestao {suggestion_id} nao encontrada")
        new_status = rules.decide(current.status, outcome, justification)
        self._suggestions.record_decision(
            suggestion_id, outcome, justification, decided_by, new_status
        )
        self._audit.append(
            current.event_id,
            "DECISION_RECORDED",
            {
                "suggestion_id": suggestion_id,
                "outcome": outcome,
                "justification": justification,
                "decided_by": decided_by,
            },
        )
        decided = self._suggestions.get(suggestion_id)
        assert decided is not None
        return decided


class GetAuditTrail:
    def __init__(self, events: EventRepository, reader: AuditReader) -> None:
        self._events = events
        self._reader = reader

    def execute(self, event_id: str) -> tuple[list[AuditEntry], bool]:
        if self._events.get(event_id) is None:
            raise EventNotFound(f"evento {event_id} nao encontrado")
        return self._reader.trail(event_id)
