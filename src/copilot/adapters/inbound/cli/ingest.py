"""CLI: indexes knowledge_base/ into the database (make ingest)."""

import argparse
import sys
from pathlib import Path

import psycopg

from copilot.adapters.outbound.llm.openrouter_embedder import OpenRouterEmbedder
from copilot.adapters.outbound.postgres.procedure_store import PostgresProcedureStore
from copilot.application.ports import EmbedderPort
from copilot.application.use_cases.ingest_procedures import IngestConflictError, ingest_procedures
from copilot.config import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest the procedure knowledge base.")
    parser.add_argument("--kb-dir", default="knowledge_base")
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="store text only (lexical search works; vector search does not)",
    )
    args = parser.parse_args(argv)
    settings = Settings()

    embedder: EmbedderPort | None = None
    if not args.no_embeddings:
        if not settings.openrouter_api_key:
            print(
                "OPENROUTER_API_KEY nao definida. Defina no .env ou use --no-embeddings.",
                file=sys.stderr,
            )
            return 2
        embedder = OpenRouterEmbedder(settings.openrouter_api_key, settings.embedding_model)

    documents = [
        p.read_text(encoding="utf-8") for p in sorted(Path(args.kb_dir).glob("PO-FICT-*.md"))
    ]
    try:
        with psycopg.connect(settings.database_url) as conn:
            report = ingest_procedures(documents, PostgresProcedureStore(conn), embedder)
    except IngestConflictError as exc:
        print(f"conflito: {exc}", file=sys.stderr)
        return 1
    mode = f"embeddings: {embedder.model}" if embedder else "sem embeddings"
    print(f"ingeridos: {len(report.ingested)}, inalterados: {len(report.unchanged)} ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
