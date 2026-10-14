from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

PENDING_REVIEW = "pending_review"
REFUSED = "refused"
APPROVED = "approved"
REJECTED = "rejected"

NO_APPLICABLE_PROCEDURE = "no_applicable_procedure"
MODEL_DECLINED = "model_declined"
NO_VALID_CITATION = "no_valid_citation"

DISCLAIMER = "Conteúdo fictício. Não usar em operação real."


@dataclass(frozen=True)
class Event:
    id: str
    type: str
    element: str
    occurred_at: datetime
    attributes: dict[str, Any]
    reported_by: str


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    procedure_code: str
    procedure_version: str
    section: str
    quote: str


@dataclass(frozen=True)
class Step:
    position: int
    instruction: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Suggestion:
    id: str
    event_id: str
    status: str
    refusal_reason: str | None
    model: str | None
    prompt_version: str | None
    steps: tuple[Step, ...] = ()
    retrieval: tuple[dict[str, Any], ...] = field(default=())
    disclaimer: str = DISCLAIMER
