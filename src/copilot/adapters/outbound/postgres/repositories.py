"""Event and suggestion persistence. Uses the caller's connection; never commits."""

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from copilot.domain.models import Citation, Event, Step, Suggestion


class PostgresEventRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def save(self, event: Event) -> None:
        self._conn.execute(
            "INSERT INTO events (id, type, element, occurred_at, attributes, reported_by)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (
                event.id,
                event.type,
                event.element,
                event.occurred_at,
                Jsonb(event.attributes),
                event.reported_by,
            ),
        )

    def get(self, event_id: str) -> Event | None:
        row = self._conn.execute(
            "SELECT id, type, element, occurred_at, attributes, reported_by FROM events"
            " WHERE id = %s",
            (event_id,),
        ).fetchone()
        if row is None:
            return None
        return Event(str(row[0]), row[1], row[2], row[3], row[4], row[5])


class PostgresSuggestionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def save(self, suggestion: Suggestion) -> None:
        self._conn.execute(
            "INSERT INTO suggestions (id, event_id, status, refusal_reason, model,"
            " prompt_version, retrieval) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                suggestion.id,
                suggestion.event_id,
                suggestion.status,
                suggestion.refusal_reason,
                suggestion.model,
                suggestion.prompt_version,
                Jsonb(list(suggestion.retrieval)),
            ),
        )
        for step in suggestion.steps:
            step_id = self._conn.execute(
                "INSERT INTO steps (suggestion_id, position, instruction)"
                " VALUES (%s, %s, %s) RETURNING id",
                (suggestion.id, step.position, step.instruction),
            ).fetchone()
            assert step_id is not None
            for c in step.citations:
                self._conn.execute(
                    "INSERT INTO citations (step_id, chunk_id, quote) VALUES (%s, %s, %s)",
                    (step_id[0], c.chunk_id, c.quote),
                )

    def get(self, suggestion_id: str, *, for_update: bool = False) -> Suggestion | None:
        lock = " FOR UPDATE" if for_update else ""
        row = self._conn.execute(
            "SELECT id, event_id, status, refusal_reason, model, prompt_version, retrieval"
            f" FROM suggestions WHERE id = %s{lock}",
            (suggestion_id,),
        ).fetchone()
        if row is None:
            return None
        return Suggestion(
            id=str(row[0]),
            event_id=str(row[1]),
            status=row[2],
            refusal_reason=row[3],
            model=row[4],
            prompt_version=row[5],
            steps=self._steps(suggestion_id),
            retrieval=tuple(row[6]),
        )

    def record_decision(
        self,
        suggestion_id: str,
        outcome: str,
        justification: str | None,
        decided_by: str,
        new_status: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO decisions (suggestion_id, outcome, justification, decided_by)"
            " VALUES (%s, %s, %s, %s)",
            (suggestion_id, outcome, justification, decided_by),
        )
        self._conn.execute(
            "UPDATE suggestions SET status = %s WHERE id = %s", (new_status, suggestion_id)
        )

    def _steps(self, suggestion_id: str) -> tuple[Step, ...]:
        rows = self._conn.execute(
            "SELECT st.position, st.instruction, ch.id, p.code, p.version, ch.section, ci.quote"
            " FROM steps st"
            " JOIN citations ci ON ci.step_id = st.id"
            " JOIN chunks ch ON ch.id = ci.chunk_id"
            " JOIN procedures p ON p.code = ch.procedure_code"
            " WHERE st.suggestion_id = %s ORDER BY st.position, ci.quote",
            (suggestion_id,),
        ).fetchall()
        grouped: dict[int, tuple[str, list[Citation]]] = {}
        for position, instruction, chunk_id, code, version, section, quote in rows:
            _, citations = grouped.setdefault(position, (instruction, []))
            citations.append(Citation(str(chunk_id), code, version, section, quote))
        steps: list[Any] = [
            Step(position=pos, instruction=text, citations=tuple(cits))
            for pos, (text, cits) in sorted(grouped.items())
        ]
        return tuple(steps)
