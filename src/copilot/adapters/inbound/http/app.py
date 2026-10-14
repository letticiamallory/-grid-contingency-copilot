import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from copilot.adapters.inbound.http import schemas
from copilot.adapters.outbound.postgres.audit import PostgresAudit
from copilot.adapters.outbound.postgres.hybrid_retriever import HybridRetriever
from copilot.adapters.outbound.postgres.lexical_retriever import LexicalRetriever
from copilot.adapters.outbound.postgres.repositories import (
    PostgresEventRepository,
    PostgresSuggestionRepository,
)
from copilot.application.ports import EmbedderPort, LLMPort, RetrieverPort
from copilot.application.use_cases.events_and_decisions import (
    GetAuditTrail,
    RecordDecision,
    RegisterEvent,
    SuggestForEvent,
)
from copilot.application.use_cases.generate_suggestion import GenerateSuggestion
from copilot.domain.errors import DomainError
from copilot.domain.models import Suggestion

_STATIC = Path(__file__).parent / "static"

_STATUS = {
    "event_not_found": 404,
    "suggestion_not_found": 404,
    "suggestion_not_pending": 409,
    "justification_required": 422,
    "llm_unavailable": 503,
    "retrieval_unavailable": 503,
}


@dataclass
class AppDeps:
    """`connect` yields a connection for one request: commit on success, rollback on error."""

    connect: Callable[[], AbstractContextManager[psycopg.Connection]]
    llm: LLMPort
    embedder: EmbedderPort | None = None  # None: lexical-only retrieval
    k: int = 6
    min_score: float = 0.0


def _error(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


def _retriever(conn: psycopg.Connection, embedder: EmbedderPort | None) -> RetrieverPort:
    return HybridRetriever(conn, embedder) if embedder else LexicalRetriever(conn)


def _suggestion_out(s: Suggestion) -> dict[str, Any]:
    return {
        "id": s.id,
        "event_id": s.event_id,
        "status": s.status,
        "refusal_reason": s.refusal_reason,
        "model": s.model,
        "prompt_version": s.prompt_version,
        "steps": [
            {
                "position": st.position,
                "instruction": st.instruction,
                "citations": [
                    {
                        "procedure_code": c.procedure_code,
                        "procedure_version": c.procedure_version,
                        "section": c.section,
                        "quote": c.quote,
                    }
                    for c in st.citations
                ],
            }
            for st in s.steps
        ],
        "disclaimer": s.disclaimer,
    }


def create_app(deps: AppDeps) -> FastAPI:
    app = FastAPI(
        title="Grid Contingency Copilot API",
        version="0.1.0",
        description="Sugere passos de resposta para eventos de rede sintéticos, com citação "
        "obrigatória e recusa explícita. Conteúdo fictício; não usar em operação real.",
    )

    @app.exception_handler(DomainError)
    def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return _error(_STATUS.get(exc.code, 500), exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    def invalid_payload(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
        return _error(400, "invalid_payload", "payload ou parâmetro inválido", {"errors": problems})

    @app.get("/", include_in_schema=False)
    def screen() -> FileResponse:
        return FileResponse(_STATIC / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/health")
    def health() -> dict[str, str]:
        with deps.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}

    @app.post("/events", status_code=201, response_model=schemas.EventOut)
    def create_event(body: schemas.EventCreate) -> Any:
        with deps.connect() as conn:
            event = RegisterEvent(PostgresEventRepository(conn), PostgresAudit(conn)).execute(
                type=body.type,
                element=body.element,
                occurred_at=body.occurred_at,
                attributes=body.attributes,
                reported_by=body.reported_by,
            )
        return event.__dict__

    @app.get("/events/{event_id}", response_model=schemas.EventOut)
    def get_event(event_id: uuid.UUID) -> Any:
        with deps.connect() as conn:
            event = PostgresEventRepository(conn).get(str(event_id))
        if event is None:
            return _error(404, "event_not_found", f"evento {event_id} nao encontrado")
        return event.__dict__

    @app.post(
        "/events/{event_id}/suggestions", status_code=201, response_model=schemas.SuggestionOut
    )
    def create_suggestion(event_id: uuid.UUID) -> Any:
        with deps.connect() as conn:
            generator = GenerateSuggestion(
                _retriever(conn, deps.embedder),
                deps.llm,
                PostgresAudit(conn),
                k=deps.k,
                min_score=deps.min_score,
            )
            suggestion = SuggestForEvent(
                PostgresEventRepository(conn), generator, PostgresSuggestionRepository(conn)
            ).execute(str(event_id))
        return _suggestion_out(suggestion)

    @app.get("/suggestions/{suggestion_id}", response_model=schemas.SuggestionOut)
    def get_suggestion(suggestion_id: uuid.UUID) -> Any:
        with deps.connect() as conn:
            suggestion = PostgresSuggestionRepository(conn).get(str(suggestion_id))
        if suggestion is None:
            return _error(404, "suggestion_not_found", f"sugestao {suggestion_id} nao encontrada")
        return _suggestion_out(suggestion)

    @app.post("/suggestions/{suggestion_id}/decision", response_model=schemas.SuggestionOut)
    def decide(suggestion_id: uuid.UUID, body: schemas.DecisionCreate) -> Any:
        with deps.connect() as conn:
            suggestion = RecordDecision(
                PostgresSuggestionRepository(conn), PostgresAudit(conn)
            ).execute(str(suggestion_id), body.outcome, body.justification, body.decided_by)
        return _suggestion_out(suggestion)

    @app.get("/events/{event_id}/audit", response_model=schemas.AuditTrailOut)
    def audit_trail(event_id: uuid.UUID) -> Any:
        with deps.connect() as conn:
            entries, valid = GetAuditTrail(
                PostgresEventRepository(conn), PostgresAudit(conn)
            ).execute(str(event_id))
        return {
            "event_id": str(event_id),
            "chain_valid": valid,
            "entries": [e.__dict__ for e in entries],
        }

    return app
