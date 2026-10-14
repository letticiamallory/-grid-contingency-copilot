from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field


class EventCreate(BaseModel):
    type: str = Field(min_length=1, examples=["line_trip_by_protection"])
    element: str = Field(min_length=1, examples=["LT-FICT-230-04"])
    occurred_at: AwareDatetime
    attributes: dict[str, Any] = Field(default_factory=dict)
    reported_by: str = Field(min_length=1)


class EventOut(EventCreate):
    id: str


class DecisionCreate(BaseModel):
    outcome: Literal["approve", "reject"]
    justification: str | None = Field(
        default=None, description="Obrigatória quando outcome = reject"
    )
    decided_by: str = Field(min_length=1)


class CitationOut(BaseModel):
    procedure_code: str
    procedure_version: str
    section: str
    quote: str = Field(description="Trecho literal presente no procedimento")


class StepOut(BaseModel):
    position: int
    instruction: str
    citations: list[CitationOut]


class SuggestionOut(BaseModel):
    id: str
    event_id: str
    status: Literal["pending_review", "refused", "approved", "rejected"]
    refusal_reason: Literal["no_applicable_procedure", "model_declined", "no_valid_citation"] | None
    model: str | None
    prompt_version: str | None
    steps: list[StepOut]
    disclaimer: str


class AuditEntryOut(BaseModel):
    seq: int
    kind: str
    at: AwareDatetime
    payload: dict[str, Any]
    hash: str


class AuditTrailOut(BaseModel):
    event_id: str
    chain_valid: bool
    entries: list[AuditEntryOut]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    error: ErrorDetail
