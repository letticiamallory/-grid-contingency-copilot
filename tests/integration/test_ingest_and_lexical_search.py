from pathlib import Path

import psycopg
import pytest

from copilot.adapters.outbound.fakes.embedder import FakeEmbedder
from copilot.adapters.outbound.postgres.lexical_retriever import LexicalRetriever
from copilot.adapters.outbound.postgres.procedure_store import PostgresProcedureStore
from copilot.application.use_cases.ingest_procedures import (
    IngestConflictError,
    ingest_procedures,
)
from copilot.config import Settings

pytestmark = pytest.mark.integration

KB = Path(__file__).resolve().parents[2] / "knowledge_base"


def _docs() -> list[str]:
    return [p.read_text(encoding="utf-8") for p in sorted(KB.glob("PO-FICT-*.md"))]


@pytest.fixture
def conn():
    """Everything runs in one transaction that is rolled back: the dev database stays untouched."""
    with psycopg.connect(Settings().database_url) as c:
        yield c
        c.rollback()


@pytest.fixture
def loaded(conn):
    # Savepoint-free: existing rows (from `make ingest`) are replaced inside the transaction.
    ingest_procedures(_docs(), PostgresProcedureStore(conn), None)
    return conn


def test_lexical_search_finds_the_right_procedure(loaded):
    results = LexicalRetriever(loaded).search(
        "religamento automático falhou, linha continua aberta", 6
    )
    codes = [r.procedure_code for r in results]
    # Recall@6 (ADR-008), not top-1: PO-FICT-001 also says "o religamento automático falhou"
    # on purpose (partial overlap), so it may rank first.
    assert "PO-FICT-002" in codes
    assert {"PO-FICT-001", "PO-FICT-002"} >= set(codes[:2])
    assert all(r.score > 0 for r in results)


def test_revoked_procedures_are_never_retrieved(loaded):
    results = LexicalRetriever(loaded).search("religar a linha imediatamente", 20)
    assert results
    assert "PO-FICT-011" not in {r.procedure_code for r in results}


def test_unrelated_text_returns_nothing(loaded):
    assert LexicalRetriever(loaded).search("receita de bolo de cenoura", 6) == []
    assert LexicalRetriever(loaded).search("!!! ???", 6) == []


def test_embeddings_are_stored_as_vectors(conn):
    ingest_procedures(_docs(), PostgresProcedureStore(conn), FakeEmbedder())
    row = conn.execute(
        "SELECT count(*) FILTER (WHERE embedding IS NOT NULL), count(*) FROM chunks"
    ).fetchone()
    assert row[0] == row[1] > 0
    dims = conn.execute("SELECT vector_dims(embedding) FROM chunks LIMIT 1").fetchone()[0]
    assert dims == 1536


def test_changing_a_cited_procedure_is_refused(loaded):
    store = PostgresProcedureStore(loaded)
    event_id = loaded.execute(
        "INSERT INTO events (type, element, occurred_at, reported_by)"
        " VALUES ('t', 'e', now(), 'tester') RETURNING id"
    ).fetchone()[0]
    suggestion_id = loaded.execute(
        "INSERT INTO suggestions (event_id, status) VALUES (%s, 'pending_review') RETURNING id",
        (event_id,),
    ).fetchone()[0]
    step_id = loaded.execute(
        "INSERT INTO steps (suggestion_id, position, instruction) VALUES (%s, 1, 'x') RETURNING id",
        (suggestion_id,),
    ).fetchone()[0]
    chunk_id = loaded.execute(
        "SELECT id FROM chunks WHERE procedure_code = 'PO-FICT-001' LIMIT 1"
    ).fetchone()[0]
    loaded.execute(
        "INSERT INTO citations (step_id, chunk_id, quote) VALUES (%s, %s, 'q')",
        (step_id, chunk_id),
    )
    changed = (
        (KB / "PO-FICT-001-linha-desligada-protecao-distancia.md")
        .read_text(encoding="utf-8")
        .replace("Registrar o horário", "Anotar o horário")
    )
    with pytest.raises(IngestConflictError):
        ingest_procedures([changed], store, None)


def test_event_type_boosts_and_selects_candidates_without_text_match(loaded):
    # Query words are English identifiers: no text match, but applies_to selects the procedures.
    results = LexicalRetriever(loaded).search("distance zone failed", 6, "line_trip_by_protection")
    codes = {r.procedure_code for r in results}
    assert "PO-FICT-001" in codes
    assert "PO-FICT-011" not in codes  # revoked, even though it applies_to the same type
    assert results[0].score >= 1.0


def test_unknown_event_type_and_no_text_match_gives_no_candidates(loaded):
    assert LexicalRetriever(loaded).search("fire in substation", 6, "substation_fire") == []
