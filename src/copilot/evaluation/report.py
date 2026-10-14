"""Aggregation and rendering of evaluation results."""

import statistics
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from copilot.evaluation import metrics as m
from copilot.evaluation.metrics import ScenarioResult

Statistic = Callable[[Sequence[ScenarioResult]], float | None]


def _refusal_p(rs: Sequence[ScenarioResult]) -> float | None:
    return m.refusal_precision_recall(rs)[0]


def _refusal_r(rs: Sequence[ScenarioResult]) -> float | None:
    return m.refusal_precision_recall(rs)[1]


def _dropped(rs: Sequence[ScenarioResult]) -> float | None:
    kept = sum(r.steps_kept for r in rs)
    dropped = sum(r.steps_dropped for r in rs)
    return dropped / (kept + dropped) if kept + dropped else None


def _format_failures(rs: Sequence[ScenarioResult]) -> float | None:
    return sum(r.format_error for r in rs) / len(rs) if rs else None


STATISTICS: dict[str, Statistic] = {
    "recall_at_k": lambda rs: m.mean([m.recall_at_k(r) for r in rs]),
    "mrr": lambda rs: m.mean([m.reciprocal_rank(r) for r in rs]),
    "steps_dropped": _dropped,
    "refusal_precision": _refusal_p,
    "refusal_recall": _refusal_r,
    "refusal_correct": lambda rs: m.mean([m.refusal_correct(r) for r in rs]),
    "hallucination": m.pooled_hallucination,
    "format_failure": _format_failures,
}


def summarize(results: Sequence[ScenarioResult]) -> dict[str, Any]:
    """Each metric: value, 95% bootstrap CI, and N of the unit of analysis' scenarios."""
    repetitions = sorted({r.repetition for r in results})
    out: dict[str, Any] = {
        "n_scenarios": len({r.scenario_id for r in results}),
        "n_repetitions": len(repetitions),
    }
    for name, statistic in STATISTICS.items():
        per_rep = [
            v
            for rep in repetitions
            if (v := statistic([r for r in results if r.repetition == rep])) is not None
        ]
        out[name] = {
            "value": statistic(results),
            "ci95": m.bootstrap_ci(results, statistic),
            "sd_across_repetitions": statistics.pstdev(per_rep) if len(per_rep) > 1 else None,
        }
    runs = len(results) or 1
    out["cost_usd_per_scenario"] = sum(r.cost_usd for r in results) / runs
    out["cost_usd_total"] = sum(r.cost_usd for r in results)
    out["tokens_per_scenario"] = sum(r.prompt_tokens + r.completion_tokens for r in results) / runs
    out["llm_calls"] = sum(r.llm_called for r in results)
    latencies = sorted(r.latency_s for r in results)
    out["latency_p50_s"] = statistics.median(latencies) if latencies else None
    out["latency_p95_s"] = latencies[int(0.95 * (len(latencies) - 1))] if latencies else None
    return out


def by_category(results: Sequence[ScenarioResult]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[ScenarioResult]] = defaultdict(list)
    for r in results:
        grouped[r.category].append(r)
    return {
        category: {
            "n": len(rs),
            "recall_at_k": STATISTICS["recall_at_k"](rs),
            "refusal_correct": STATISTICS["refusal_correct"](rs),
            "hallucination": STATISTICS["hallucination"](rs),
        }
        for category, rs in sorted(grouped.items())
    }


def _cell(metric: dict[str, Any]) -> str:
    value, ci, sd = metric["value"], metric["ci95"], metric.get("sd_across_repetitions")
    if value is None:
        return "n/a"
    text = f"{value:.2f} [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else f"{value:.2f}"
    return f"{text}, dp entre repeticoes {sd:.2f}" if sd is not None else text


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def render_markdown(
    title: str, meta: dict[str, Any], summary: dict[str, Any], categories: dict[str, Any]
) -> str:
    lines = [f"# {title}", ""]
    lines += [f"- {key}: {value}" for key, value in meta.items()]
    lines += [
        "",
        f"N de cenarios: {summary['n_scenarios']}. Celulas: valor [IC 95% bootstrap].",
        "",
    ]
    lines += ["| Metrica | Resultado |", "|---|---|"]
    labels = {
        "recall_at_k": "Recall@k",
        "mrr": "MRR",
        "steps_dropped": "Passos descartados",
        "refusal_precision": "Recusa: precisao",
        "refusal_recall": "Recusa: recall",
        "refusal_correct": "Decisao de recusa correta",
        "hallucination": "Alucinacao (limite inferior)",
        "format_failure": "Falha de formato",
    }
    lines += [f"| {labels[key]} | {_cell(summary[key])} |" for key in labels]
    lines += [
        f"| Latencia p50 / p95 (s) | {_fmt(summary['latency_p50_s'])} / "
        f"{_fmt(summary['latency_p95_s'])} |",
        f"| Custo por cenario / total (US$) | {summary['cost_usd_per_scenario']:.5f} / "
        f"{summary['cost_usd_total']:.4f} |",
        f"| Tokens por cenario | {summary['tokens_per_scenario']:.0f} |",
        "",
        "## Por categoria",
        "",
        "| Categoria | N | Recall@k | Recusa correta | Alucinacao |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {name} | {c['n']} | {_fmt(c['recall_at_k'])} | {_fmt(c['refusal_correct'])} | "
        f"{_fmt(c['hallucination'])} |"
        for name, c in categories.items()
    ]
    return "\n".join(lines) + "\n"
