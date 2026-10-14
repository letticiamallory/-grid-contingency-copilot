from pathlib import Path

import pytest

from copilot.adapters.outbound.fakes.embedder import FakeEmbedder
from copilot.adapters.outbound.postgres.hybrid_retriever import HybridRetriever
from copilot.adapters.outbound.postgres.procedure_store import PostgresProcedureStore
from copilot.application.use_cases.ingest_procedures import ingest_procedures
from copilot.domain.errors import RetrievalUnavailable

pytestmark = pytest.mark.integration

KB = Path(__file__).resolve().parents[2] / "knowledge_base"


@pytest.fixture
def embedded(db):
    docs = [p.read_text(encoding="utf-8") for p in sorted(KB.glob("PO-FICT-*.md"))]
    ingest_procedures(docs, PostgresProcedureStore(db), FakeEmbedder())
    return db


def test_typed_procedure_comes_first_with_boosted_score(embedded):
    results = HybridRetriever(embedded, FakeEmbedder()).search(
        "distance zone failed", 6, "line_trip_by_protection"
    )
    assert results[0].procedure_code in {"PO-FICT-001", "PO-FICT-002"}
    assert results[0].score >= 1.0


def test_unknown_type_scores_stay_far_below_the_type_boost(embedded):
    results = HybridRetriever(embedded, FakeEmbedder()).search(
        "fire in substation", 6, "substation_fire"
    )
    assert results and results[0].score < 0.1


def test_revoked_procedures_never_appear(embedded):
    results = HybridRetriever(embedded, FakeEmbedder()).search(
        "religar a linha", 30, "line_trip_by_protection"
    )
    assert "PO-FICT-011" not in {r.procedure_code for r in results}


def test_lexical_candidates_take_part_in_the_fusion(embedded):
    text = "Confirmar a posição dos disjuntores em ambas as extremidades da linha"
    results = HybridRetriever(embedded, FakeEmbedder()).search(text, 30)
    # Fake embeddings are noise, so the order is not asserted: only that the lexical match
    # reaches the fused list. Ranking quality needs real embeddings (see the evaluation).
    assert "PO-FICT-001" in {r.procedure_code for r in results}


def test_embedding_failure_is_not_silently_replaced_by_lexical_results(embedded):
    class Broken:
        model = "broken"

        def embed(self, texts):
            raise RuntimeError("down")

    with pytest.raises(RetrievalUnavailable):
        HybridRetriever(embedded, Broken()).search("qualquer", 6)
