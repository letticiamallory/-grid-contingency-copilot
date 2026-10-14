"""Runs scenarios through the real use case and calibrates the refusal threshold."""

import json
import time
from collections.abc import Sequence
from pathlib import Path

from copilot.adapters.outbound.fakes.audit import InMemoryAudit
from copilot.application.ports import LLMPort, RetrieverPort
from copilot.application.use_cases.generate_suggestion import GenerateSuggestion
from copilot.domain import models
from copilot.domain.models import Event
from copilot.domain.procedures import RetrievedChunk
from copilot.evaluation.metrics import ScenarioResult
from copilot.evaluation.scenarios import Scenario


class _RecordingRetriever:
    def __init__(self, inner: RetrieverPort) -> None:
        self._inner = inner
        self.last: list[RetrievedChunk] = []

    def search(self, query: str, k: int, event_type: str | None = None) -> list[RetrievedChunk]:
        self.last = self._inner.search(query, k, event_type)
        return self.last


def event_of(s: Scenario) -> Event:
    return Event(
        id=s.id,
        type=s.event_type,
        element=s.element,
        occurred_at=s.occurred_at,
        attributes=s.attributes,
        reported_by="evaluation",
    )


def run_scenario(
    s: Scenario, retriever: RetrieverPort, llm: LLMPort, *, k: int, min_score: float
) -> ScenarioResult:
    recorder = _RecordingRetriever(retriever)
    audit = InMemoryAudit()
    started = time.perf_counter()
    suggestion = GenerateSuggestion(recorder, llm, audit, k=k, min_score=min_score).execute(
        event_of(s)
    )
    latency = time.perf_counter() - started

    validated = next((p for _, kind, p in audit.entries if kind == "CITATIONS_VALIDATED"), {})
    chunks = recorder.last
    return ScenarioResult(
        scenario_id=s.id,
        category=s.category,
        split=s.split,
        expected_refusal=s.refusal,
        expected_procedures=s.procedures,
        retrieved_procedures=tuple(c.procedure_code for c in chunks),
        top_score=chunks[0].score if chunks else None,
        refused=suggestion.status == models.REFUSED,
        refusal_reason=suggestion.refusal_reason,
        steps_kept=int(validated.get("steps_kept", 0)),
        steps_dropped=int(validated.get("steps_dropped", 0)),
        format_error=bool(validated.get("format_error", False)),
        accepted_steps=tuple(
            (st.instruction, tuple(c.procedure_code for c in st.citations))
            for st in suggestion.steps
        ),
        forbidden_steps=s.forbidden_steps,
        latency_s=latency,
    )


def run_all(
    scenarios: Sequence[Scenario],
    retriever: RetrieverPort,
    llm: LLMPort,
    *,
    k: int,
    min_score: float,
) -> list[ScenarioResult]:
    return [run_scenario(s, retriever, llm, k=k, min_score=min_score) for s in scenarios]


def calibrate_threshold(results: Sequence[ScenarioResult]) -> tuple[float, float]:
    """Picks the retrieval-score threshold that maximises correct refusal decisions on the
    calibration results (run with min_score=0). Returns (threshold, accuracy). Every observed
    top score is a candidate; the optimum is usually a whole range of equivalent thresholds, so
    the midpoint of the first optimal range is used (robust to scores near either edge). Only
    top_score and the expected outcome are used, so the choice does not depend on the
    generation model."""
    if not results:
        raise ValueError("calibration needs at least one scenario")
    candidates = sorted({0.0, *(r.top_score for r in results if r.top_score is not None)})
    accuracies = [
        sum(
            ((r.top_score is None or r.top_score < threshold) == r.expected_refusal)
            for r in results
        )
        / len(results)
        for threshold in candidates
    ]
    best = max(accuracies)
    first = accuracies.index(best)
    last = first
    while last + 1 < len(candidates) and accuracies[last + 1] == best:
        last += 1
    # A threshold t refuses scores < t, so every t in (candidates[first-1], candidates[last]]
    # makes the same decisions as candidates[first..last]; take the middle of that interval.
    lower = candidates[first - 1] if first > 0 else 0.0
    return (lower + candidates[last]) / 2, best


def save_threshold(path: Path, threshold: float, accuracy: float, n: int) -> None:
    path.write_text(
        json.dumps(
            {"min_score": threshold, "calibration_accuracy": accuracy, "n_scenarios": n},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_threshold(path: Path) -> float:
    return float(json.loads(path.read_text(encoding="utf-8"))["min_score"])
