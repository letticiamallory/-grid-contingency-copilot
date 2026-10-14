"""CLI: evaluation harness (make eval-fake / eval-calibrate / eval).

calibrate  sweeps the refusal threshold on the calibration split and saves it.
run        evaluates a split with the saved threshold and writes a report.
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import psycopg

from copilot.adapters.outbound.fakes.llm import EchoLLM
from copilot.adapters.outbound.postgres.lexical_retriever import LexicalRetriever
from copilot.application.ports import LLMPort
from copilot.application.prompting import PROMPT_VERSION
from copilot.config import Settings
from copilot.evaluation import report
from copilot.evaluation.runner import (
    calibrate_threshold,
    load_threshold,
    run_all,
    save_threshold,
)
from copilot.evaluation.scenarios import load_scenarios, structural_problems

K = 6


def _llm(name: str) -> LLMPort:
    if name == "echo":
        return EchoLLM()
    raise SystemExit(
        f"LLM '{name}' indisponivel: so o modo 'echo' (somente encanamento) esta implementado."
    )


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
    parser.add_argument("--threshold-file", type=Path, default=Path("eval/threshold.json"))
    parser.add_argument("--reports-dir", type=Path, default=Path("eval/reports"))
    parser.add_argument("--split", choices=["calibration", "test"], default="test")
    parser.add_argument("--llm", default="echo")
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.scenarios_dir)
    problems = structural_problems(scenarios)
    for problem in problems:
        print(f"AVISO: {problem}", file=sys.stderr)

    with psycopg.connect(Settings().database_url, connect_timeout=5) as conn:
        retriever = LexicalRetriever(conn)
        if args.command == "calibrate":
            chosen = [s for s in scenarios if s.split == "calibration"]
            results = run_all(chosen, retriever, _llm(args.llm), k=K, min_score=0.0)
            threshold, accuracy = calibrate_threshold(results)
            save_threshold(args.threshold_file, threshold, accuracy, len(results))
            print(f"limiar={threshold:.4f} acuracia_calibracao={accuracy:.2f} N={len(results)}")
            return 0

        min_score = load_threshold(args.threshold_file)
        chosen = [s for s in scenarios if s.split == args.split]
        results = run_all(chosen, retriever, _llm(args.llm), k=K, min_score=min_score)

    summary = report.summarize(results)
    categories = report.by_category(results)
    meta = {
        "data": date.today().isoformat(),
        "commit": _commit(),
        "split": args.split,
        "llm": args.llm,
        "prompt_version": PROMPT_VERSION,
        "limiar_de_recusa": min_score,
        "recuperacao": "lexical (PostgreSQL full-text)",
        "autoria_dos_cenarios": "rascunhos do assistente, nao revisados (ADR-008)",
    }
    if args.llm == "echo":
        meta["aviso"] = "LLM de eco: mede apenas recuperacao, recusa e encanamento, nao qualidade"
    title = f"Avaliacao {meta['data']} ({args.llm}, {args.split})"
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    stem = args.reports_dir / f"{meta['data']}-{args.llm}-{args.split}"
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
