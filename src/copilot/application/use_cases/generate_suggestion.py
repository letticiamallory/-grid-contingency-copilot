import json
import re
import uuid
from typing import Any

from copilot.application.ports import AuditPort, LLMPort, RetrieverPort
from copilot.application.prompting import PROMPT_VERSION, build_search_query, render_prompt
from copilot.domain import models
from copilot.domain.citation import quote_is_in
from copilot.domain.models import Citation, Event, Step, Suggestion
from copilot.domain.procedures import RetrievedChunk

_FENCE = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.DOTALL)


class GenerateSuggestion:
    """Retrieve -> (refuse | generate -> validate citations -> (refuse | suggest)).

    Refusing is a normal result, not an error. LLM failures propagate as exceptions: they must
    never turn into a suggestion without citations (ADR-005).
    """

    def __init__(
        self,
        retriever: RetrieverPort,
        llm: LLMPort,
        audit: AuditPort,
        *,
        k: int = 6,
        min_score: float = 0.0,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._audit = audit
        self._k = k
        # Placeholder: the real refusal threshold is calibrated on the evaluation set (ADR-003).
        self._min_score = min_score

    def execute(self, event: Event) -> Suggestion:
        chunks = self._retriever.search(build_search_query(event), self._k, event.type)
        retrieval = tuple(
            {"chunk_id": c.chunk_id, "procedure": c.procedure_code, "score": c.score}
            for c in chunks
        )
        self._audit.append(event.id, "RETRIEVAL_DONE", {"results": list(retrieval)})

        if not chunks or chunks[0].score < self._min_score:
            return self._refuse(event, models.NO_APPLICABLE_PROCEDURE, retrieval)

        system, user = render_prompt(event, chunks)
        response = self._llm.complete(system, user)
        self._audit.append(
            event.id,
            "LLM_CALLED",
            {"model": response.model, "prompt_version": PROMPT_VERSION},
        )

        parsed = _parse(response.text)
        if parsed is None:
            self._audit.append(event.id, "CITATIONS_VALIDATED", {"format_error": True})
            return self._refuse(
                event, models.NO_VALID_CITATION, retrieval, response.model, format_error=True
            )
        if parsed.get("refusal"):
            return self._refuse(event, models.MODEL_DECLINED, retrieval, response.model)

        steps, dropped = _validate(parsed.get("steps"), {c.chunk_id: c for c in chunks})
        self._audit.append(
            event.id,
            "CITATIONS_VALIDATED",
            {"steps_kept": len(steps), "steps_dropped": dropped},
        )
        if not steps:
            return self._refuse(event, models.NO_VALID_CITATION, retrieval, response.model)

        suggestion = Suggestion(
            id=str(uuid.uuid4()),
            event_id=event.id,
            status=models.PENDING_REVIEW,
            refusal_reason=None,
            model=response.model,
            prompt_version=PROMPT_VERSION,
            steps=tuple(steps),
            retrieval=retrieval,
        )
        self._audit.append(event.id, "SUGGESTION_CREATED", {"suggestion_id": suggestion.id})
        return suggestion

    def _refuse(
        self,
        event: Event,
        reason: str,
        retrieval: tuple[dict[str, Any], ...],
        model: str | None = None,
        *,
        format_error: bool = False,
    ) -> Suggestion:
        suggestion = Suggestion(
            id=str(uuid.uuid4()),
            event_id=event.id,
            status=models.REFUSED,
            refusal_reason=reason,
            model=model,
            prompt_version=PROMPT_VERSION if model else None,
            retrieval=retrieval,
        )
        payload: dict[str, Any] = {"suggestion_id": suggestion.id, "reason": reason}
        if format_error:
            payload["format_error"] = True
        self._audit.append(event.id, "REFUSED", payload)
        return suggestion


def _parse(text: str) -> dict[str, Any] | None:
    body = text.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group(1)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _validate(raw_steps: Any, by_id: dict[str, RetrievedChunk]) -> tuple[list[Step], int]:
    """Keeps only citations whose chunk was retrieved and whose quote is literally in it.
    A step with no valid citation is dropped."""
    if not isinstance(raw_steps, list):
        return [], 0
    kept: list[Step] = []
    dropped = 0
    for raw in raw_steps:
        citations = _valid_citations(raw, by_id)
        instruction = raw.get("instruction") if isinstance(raw, dict) else None
        if not citations or not isinstance(instruction, str) or not instruction.strip():
            dropped += 1
            continue
        kept.append(
            Step(position=len(kept) + 1, instruction=instruction.strip(), citations=citations)
        )
    return kept, dropped


def _valid_citations(raw_step: Any, by_id: dict[str, RetrievedChunk]) -> tuple[Citation, ...]:
    if not isinstance(raw_step, dict) or not isinstance(raw_step.get("citations"), list):
        return ()
    valid: list[Citation] = []
    for c in raw_step["citations"]:
        if not isinstance(c, dict):
            continue
        chunk = by_id.get(str(c.get("chunk_id")))
        quote = c.get("quote")
        if chunk and isinstance(quote, str) and quote_is_in(quote, chunk.text):
            valid.append(
                Citation(
                    chunk_id=chunk.chunk_id,
                    procedure_code=chunk.procedure_code,
                    procedure_version=chunk.procedure_version,
                    section=chunk.section,
                    quote=quote.strip(),
                )
            )
    return tuple(valid)
