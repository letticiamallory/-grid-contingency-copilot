"""CLI: evaluation harness (make eval-fake / eval-calibrate / eval).

calibrate  sweeps the refusal threshold on the calibration split (retrieval only, no LLM cost)
           and saves it, one file per retrieval mode.
run        evaluates a split and writes a report. `--mode norag` is the no-retrieval baseline.
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

import psycopg

from copilot.adapters.outbound.fakes.llm import EchoLLM
from copilot.adapters.outbound.llm.cached import CachedLLM
from copilot.adapters.outbound.llm.openrouter_embedder import OpenRouterEmbedder
from copilot.adapters.outbound.llm.openrouter_llm import OpenRouterLLM
from copilot.adapters.outbound.postgres.catalog import PostgresCatalog
from copilot.adapters.outbound.postgres.hybrid_retriever import HybridRetriever
from copilot.adapters.outbound.postgres.lexical_retriever import LexicalRetriever
from copilot.application.ports import LLMPort, RetrieverPort
from copilot.application.prompting import PROMPT_VERSION
from copilot.application.use_cases.generate_without_retrieval import NORAG_PROMPT_VERSION
from copilot.config import Settings
from copilot.evaluation import report
from copilot.evaluation.metrics import ScenarioResult
from copilot.evaluation.runner import (
    calibrate_threshold,
    load_threshold,
    run_all,
    run_scenario,
    run_scenario_without_retrieval,
    save_threshold,
)
from copilot.evaluation.scenarios import Scenario, load_scenarios, structural_problems

K = 6


def _llm_factory(name: str, cache_dir: Path | None) -> Callable[[int], LLMPort]:
    """`echo` (pipeline only) or `openrouter:<model-id>`; never with fallback (docs/03).
    Each repetition gets its own cache salt, so repetitions are real calls the first time."""
    if name == "echo":
        return lambda rep: EchoLLM()
    if name.startswith("openrouter:"):
        key = Settings().openrouter_api_key
        if not key:
            raise SystemExit("OPENROUTER_API_KEY nao configurada.")
        model = name.removeprefix("openrouter:")
        inner = OpenRouterLLM(key, model)

        def build(rep: int) -> LLMPort:
            if cache_dir is None:
                return inner
            return CachedLLM(inner, model, cache_dir, salt=str(rep))

        return build
    raise SystemExit(f"LLM desconhecido: {name!r} (use 'echo' ou 'openrouter:<modelo>')")


def _retriever(name: str, conn: psycopg.Connection) -> RetrieverPort:
    if name == "lexical":
        return LexicalRetriever(conn)
    settings = Settings()
    if not settings.openrouter_api_key:
        raise SystemExit("OPENROUTER_API_KEY nao configurada (necessaria para hybrid).")
    embedder = OpenRouterEmbedder(settings.openrouter_api_key, settings.embedding_model)
    return HybridRetriever(conn, embedder)


def _commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evaluate")
    parser.add_argument("command", choices=["calibrate", "run"])
    parser.add_argument("--scenarios-dir", type=Path, default=Path("eval/scenarios"))
    parser.add_argument("--mode", choices=["rag", "norag"], default="rag")
    parser.add_argument("--retrieval", choices=["lexical", "hybrid"], default="lexical")
    parser.add_argument("--threshold-file", type=Path, default=None)
    parser.add_argument("--reports-dir", type=Path, default=Path("eval/reports"))
    parser.add_argument("--split", choices=["calibration", "test"], default="test")
    parser.add_argument("--llm", default="echo")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--cache-dir", type=Path, default=Path("eval/cache"))
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)
    # Score scales differ between retrievers, so each has its own calibrated threshold.
    args.threshold_file = args.threshold_file or Path(f"eval/threshold-{args.retrieval}.json")

    scenarios = load_scenarios(args.scenarios_dir)
    for problem in structural_problems(scenarios):
        print(f"AVISO: {problem}", file=sys.stderr)

    min_score: float | None = None
    with psycopg.connect(Settings().database_url, connect_timeout=5) as conn:
        if args.command == "calibrate":
            retriever = _retriever(args.retrieval, conn)
            chosen = [s for s in scenarios if s.split == "calibration"]
            results = run_all(
                chosen,
                lambda s, rep: run_scenario(s, retriever, EchoLLM(), k=K, min_score=0.0),
            )
            threshold, accuracy = calibrate_threshold(results)
            save_threshold(args.threshold_file, threshold, accuracy, len(results))
            print(f"limiar={threshold:.4f} acuracia_calibracao={accuracy:.2f} N={len(results)}")
            return 0

        chosen = [s for s in scenarios if s.split == args.split]
        llm_for = _llm_factory(args.llm, None if args.no_cache else args.cache_dir)
        run_one: Callable[[Scenario, int], ScenarioResult]
        if args.mode == "rag":
            rag_retriever = _retriever(args.retrieval, conn)
            min_score = load_threshold(args.threshold_file)
            floor = min_score

            def run_one(s: Scenario, rep: int) -> ScenarioResult:
                return run_scenario(s, rag_retriever, llm_for(rep), k=K, min_score=floor)
        else:
            catalog = PostgresCatalog(conn)

            def run_one(s: Scenario, rep: int) -> ScenarioResult:
                return run_scenario_without_retrieval(s, catalog, llm_for(rep))

        results = run_all(chosen, run_one, repetitions=args.reps)

    summary = report.summarize(results)
    categories = report.by_category(results)
    meta = {
        "data": date.today().isoformat(),
        "commit": _commit(),
        "split": args.split,
        "modo": args.mode,
        "llm": args.llm,
        "prompt_version": PROMPT_VERSION if args.mode == "rag" else NORAG_PROMPT_VERSION,
        "limiar_de_recusa": min_score if min_score is not None else "n/a (sem recuperacao)",
        "recuperacao": args.retrieval if args.mode == "rag" else "nenhuma (so codigos e titulos)",
        "repeticoes": args.reps,
        "temperatura": 0,
        "fallback": "desligado",
        "autoria_dos_cenarios": "rascunhos do assistente, nao revisados (ADR-008)",
    }
    if args.llm == "echo":
        meta["aviso"] = "LLM de eco: mede apenas recuperacao, recusa e encanamento, nao qualidade"
    tag = f"rag-{args.retrieval}" if args.mode == "rag" else "norag"
    title = f"Avaliacao {meta['data']} ({args.llm}, {tag}, {args.split})"
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    safe_llm = args.llm.replace(":", "_").replace("/", "_").replace(".", "-")
    stem = args.reports_dir / f"{meta['data']}-{safe_llm}-{tag}-{args.split}"
    stem.with_suffix(".md").write_text(
        report.render_markdown(title, meta, summary, categories), encoding="utf-8"
    )
    stem.with_suffix(".json").write_text(
        json.dumps(
            {"meta": meta, "summary": summary, "categories": categories}, indent=2, default=str
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"relatorio: {stem.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
