import json
import uuid
from string import Template
from typing import Any

from copilot.application.ports import AuditPort, CatalogEntry, CatalogPort, LLMPort
from copilot.application.prompting import PROMPTS_DIR
from copilot.application.use_cases.generate_suggestion import parse_model_json
from copilot.domain import models
from copilot.domain.citation import quote_is_in
from copilot.domain.models import Citation, Event, Step, Suggestion
from copilot.domain.procedures import RetrievedChunk

NORAG_PROMPT_VERSION = "norag1"


class GenerateWithoutRetrieval:
    """Evaluation baseline (docs/03, "sem RAG"): the model sees the event and the list of
    procedure codes and titles, but not their text. Citations are still verified against the
    whole base: a quote must literally exist in the cited procedure. Measures how much the model
    invents without grounding. Not part of the production flow."""

    def __init__(self, catalog: CatalogPort, llm: LLMPort, audit: AuditPort) -> None:
        self._catalog = catalog
        self._llm = llm
        self._audit = audit

    def execute(self, event: Event) -> Suggestion:
        entries = self._catalog.valid_procedures()
        system = (PROMPTS_DIR / f"{NORAG_PROMPT_VERSION}.system.md").read_text(encoding="utf-8")
        template = Template(
            (PROMPTS_DIR / f"{NORAG_PROMPT_VERSION}.user.md").read_text(encoding="utf-8")
        )
        event_json = json.dumps(
            {
                "tipo": event.type,
                "elemento": event.element,
                "ocorrido_em": event.occurred_at.isoformat(),
                "atributos": event.attributes,
            },
            ensure_ascii=False,
            indent=2,
        )
        catalog_text = "\n".join(f"- {e.code} v{e.version}: {e.title}" for e in entries)
        response = self._llm.complete(
            system, template.substitute(event=event_json, catalog=catalog_text)
        )
        self._audit.append(
            event.id,
            "LLM_CALLED",
            {"model": response.model, "prompt_version": NORAG_PROMPT_VERSION},
        )

        parsed = parse_model_json(response.text)
        if parsed is None:
            self._audit.append(event.id, "CITATIONS_VALIDATED", {"format_error": True})
            return self._refuse(event, models.NO_VALID_CITATION, response.model)
        if parsed.get("refusal"):
            return self._refuse(event, models.MODEL_DECLINED, response.model)

        steps, dropped = self._validate(parsed.get("steps"), {e.code: e for e in entries})
        self._audit.append(
            event.id, "CITATIONS_VALIDATED", {"steps_kept": len(steps), "steps_dropped": dropped}
        )
        if not steps:
            return self._refuse(event, models.NO_VALID_CITATION, response.model)
        return Suggestion(
            id=str(uuid.uuid4()),
            event_id=event.id,
            status=models.PENDING_REVIEW,
            refusal_reason=None,
            model=response.model,
            prompt_version=NORAG_PROMPT_VERSION,
            steps=tuple(steps),
        )

    def _refuse(self, event: Event, reason: str, model: str) -> Suggestion:
        suggestion = Suggestion(
            id=str(uuid.uuid4()),
            event_id=event.id,
            status=models.REFUSED,
            refusal_reason=reason,
            model=model,
            prompt_version=NORAG_PROMPT_VERSION,
        )
        self._audit.append(event.id, "REFUSED", {"reason": reason})
        return suggestion

    def _validate(self, raw_steps: Any, by_code: dict[str, CatalogEntry]) -> tuple[list[Step], int]:
        if not isinstance(raw_steps, list):
            return [], 0
        kept: list[Step] = []
        dropped = 0
        for raw in raw_steps:
            citations = self._citations(raw, by_code)
            instruction = raw.get("instruction") if isinstance(raw, dict) else None
            if not citations or not isinstance(instruction, str) or not instruction.strip():
                dropped += 1
                continue
            kept.append(
                Step(position=len(kept) + 1, instruction=instruction.strip(), citations=citations)
            )
        return kept, dropped

    def _citations(self, raw_step: Any, by_code: dict[str, CatalogEntry]) -> tuple[Citation, ...]:
        if not isinstance(raw_step, dict) or not isinstance(raw_step.get("citations"), list):
            return ()
        valid: list[Citation] = []
        for c in raw_step["citations"]:
            if not isinstance(c, dict) or str(c.get("procedure_code")) not in by_code:
                continue
            quote = c.get("quote")
            if not isinstance(quote, str):
                continue
            chunk = self._chunk_with(str(c["procedure_code"]), quote)
            if chunk:
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

    def _chunk_with(self, code: str, quote: str) -> RetrievedChunk | None:
        return next((c for c in self._catalog.chunks_of(code) if quote_is_in(quote, c.text)), None)
