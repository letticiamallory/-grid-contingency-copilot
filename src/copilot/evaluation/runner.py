"""Runs scenarios through the real use cases and calibrates the refusal threshold."""

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from copilot.adapters.outbound.fakes.audit import InMemoryAudit
from copilot.application.ports import CatalogPort, LLMPort, LLMResponse, RetrieverPort
from copilot.application.use_cases.generate_suggestion import GenerateSuggestion
from copilot.application.use_cases.generate_without_retrieval import GenerateWithoutRetrieval
from copilot.domain import models
from copilot.domain.models import Event, Suggestion
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


class _RecordingLLM:
    def __init__(self, inner: LLMPort) -> None:
        self._inner = inner
        self.responses: list[LLMResponse] = []

    def complete(self, system: str, user: str) -> LLMResponse:
        response = self._inner.complete(system, user)
        self.responses.append(response)
        return response


def event_of(s: Scenario) -> Event:
    return Event(
        id=s.id,
        type=s.event_type,
        element=s.element,
        occurred_at=s.occurred_at,
        attributes=s.attributes,
        reported_by="evaluation",
    )


def _result(
    s: Scenario,
    suggestion: Suggestion,
    audit: InMemoryAudit,
    llm: _RecordingLLM,
    chunks: list[RetrievedChunk],
    *,
    retrieval_used: bool,
    latency: float,
) -> ScenarioResult:
    validated = next((p for _, kind, p in audit.entries if kind == "CITATIONS_VALIDATED"), {})
    responses = llm.responses
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
        # Latency of the model call when known (cached runs keep the original), else wall time.
        latency_s=sum(r.latency_s or 0.0 for r in responses) or latency,
        retrieval_used=retrieval_used,
        prompt_tokens=sum(r.prompt_tokens or 0 for r in responses),
        completion_tokens=sum(r.completion_tokens or 0 for r in responses),
        cost_usd=sum(r.cost_usd or 0.0 for r in responses),
        llm_called=bool(responses),
    )


def run_scenario(
    s: Scenario, retriever: RetrieverPort, llm: LLMPort, *, k: int, min_score: float
) -> ScenarioResult:
    recorder = _RecordingRetriever(retriever)
    recording_llm = _RecordingLLM(llm)
    audit = InMemoryAudit()
    started = time.perf_counter()
    suggestion = GenerateSuggestion(
        recorder, recording_llm, audit, k=k, min_score=min_score
    ).execute(event_of(s))
    latency = time.perf_counter() - started
    return _result(
        s, suggestion, audit, recording_llm, recorder.last, retrieval_used=True, latency=latency
    )


def run_scenario_without_retrieval(
    s: Scenario, catalog: CatalogPort, llm: LLMPort
) -> ScenarioResult:
    recording_llm = _RecordingLLM(llm)
    audit = InMemoryAudit()
    started = time.perf_counter()
    suggestion = GenerateWithoutRetrieval(catalog, recording_llm, audit).execute(event_of(s))
    latency = time.perf_counter() - started
    return _result(s, suggestion, audit, recording_llm, [], retrieval_used=False, latency=latency)


def run_all(
    scenarios: Sequence[Scenario],
    run_one: Callable[[Scenario, int], ScenarioResult],
    *,
    repetitions: int = 1,
) -> list[ScenarioResult]:
    """`run_one(scenario, repetition)`; every result is tagged with its repetition index."""
    return [
        replace(run_one(s, rep), repetition=rep) for rep in range(repetitions) for s in scenarios
    ]


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
