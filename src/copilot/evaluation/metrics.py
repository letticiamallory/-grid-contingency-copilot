"""Pure metric functions (docs/03). No I/O; everything is computed from per-scenario results."""

import random
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from copilot.domain.citation import normalize


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    category: str
    split: str
    expected_refusal: bool
    expected_procedures: tuple[str, ...]
    retrieved_procedures: tuple[str, ...]  # procedure code per retrieved chunk, in rank order
    top_score: float | None
    refused: bool
    refusal_reason: str | None
    steps_kept: int
    steps_dropped: int
    format_error: bool
    accepted_steps: tuple[tuple[str, tuple[str, ...]], ...]  # (instruction, cited procedure codes)
    forbidden_steps: tuple[str, ...]
    latency_s: float = 0.0
    retrieval_used: bool = True
    repetition: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    llm_called: bool = False


def recall_at_k(r: ScenarioResult) -> float | None:
    if r.expected_refusal or not r.retrieval_used:
        return None
    return float(any(code in r.expected_procedures for code in r.retrieved_procedures))


def reciprocal_rank(r: ScenarioResult) -> float | None:
    if r.expected_refusal or not r.retrieval_used:
        return None
    for position, code in enumerate(r.retrieved_procedures, start=1):
        if code in r.expected_procedures:
            return 1 / position
    return 0.0


def refusal_correct(r: ScenarioResult) -> float:
    return float(r.refused == r.expected_refusal)


def dropped_fraction(r: ScenarioResult) -> float | None:
    total = r.steps_kept + r.steps_dropped
    return r.steps_dropped / total if total else None


def hallucinated_steps(r: ScenarioResult) -> tuple[int, int]:
    """(hallucinated, accepted). A step is hallucinated when it matches a forbidden step or
    cites a procedure outside the expected set (any accepted step in a refusal scenario).
    Lower bound: a validly cited but semantically wrong step is not counted."""
    forbidden = [fold(f) for f in r.forbidden_steps]
    bad = 0
    for instruction, cited in r.accepted_steps:
        text = fold(instruction)
        off_procedure = r.expected_refusal or any(c not in r.expected_procedures for c in cited)
        if off_procedure or any(_affirms(text, f) for f in forbidden):
            bad += 1
    return bad, len(r.accepted_steps)


def fold(text: str) -> str:
    """normalize() plus accent stripping: scenario files are written without accents, model
    output has them. Only for the hallucination metric; citation checks stay accent-strict."""
    decomposed = unicodedata.normalize("NFKD", normalize(text))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


_NEGATORS = ("nao ", "nunca ", "evitar ", "evite ", "sem ", "impedir ", "proibido ")


def _affirms(text: str, forbidden: str) -> bool:
    """True when `forbidden` occurs in `text` outside a negation: "nao religar a linha" does not
    count as recommending to reconnect. Heuristic: a negator within the 30 characters before
    the phrase. Misses long-distance negation, so the metric stays a lower bound."""
    start = text.find(forbidden)
    while start != -1:
        before = text[max(0, start - 30) : start]
        if not any(n in before for n in _NEGATORS):
            return True
        start = text.find(forbidden, start + 1)
    return False


def refusal_precision_recall(
    results: Sequence[ScenarioResult],
) -> tuple[float | None, float | None]:
    refused = [r for r in results if r.refused]
    should = [r for r in results if r.expected_refusal]
    correct = sum(r.expected_refusal for r in refused)
    precision = correct / len(refused) if refused else None
    recall = sum(r.refused for r in should) / len(should) if should else None
    return precision, recall


def mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def pooled_hallucination(results: Sequence[ScenarioResult]) -> float | None:
    bad = accepted = 0
    for r in results:
        b, a = hallucinated_steps(r)
        bad, accepted = bad + b, accepted + a
    return bad / accepted if accepted else None


def bootstrap_ci(
    results: Sequence[ScenarioResult],
    statistic: Callable[[Sequence[ScenarioResult]], float | None],
    *,
    resamples: int = 1000,
    seed: int = 0,
) -> tuple[float, float] | None:
    """95% percentile bootstrap, resampling scenarios (all repetitions of a scenario travel
    together, since they are not independent). None when the statistic is undefined."""
    if not results:
        return None
    groups: dict[str, list[ScenarioResult]] = {}
    for r in results:
        groups.setdefault(r.scenario_id, []).append(r)
    clusters = list(groups.values())
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(resamples):
        sample = [r for _ in clusters for r in clusters[rng.randrange(len(clusters))]]
        value = statistic(sample)
        if value is not None:
            stats.append(value)
    if not stats:
        return None
    stats.sort()
    return stats[int(0.025 * (len(stats) - 1))], stats[int(0.975 * (len(stats) - 1))]
