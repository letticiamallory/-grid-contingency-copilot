from copilot.adapters.outbound.fakes.embedder import FakeEmbedder
from copilot.adapters.outbound.fakes.procedure_store import InMemoryProcedureStore
from copilot.application.use_cases.ingest_procedures import ingest_procedures

DOC = """---
code: PO-FICT-900
title: Exemplo
version: "1.0"
status: vigente
ficticio: true
applies_to: [evento_x]
---

> Conteúdo fictício.

## 1. Objetivo
Texto.

## 4. Ações
1. Passo um.
"""


def test_ingests_with_one_embedding_per_chunk():
    store = InMemoryProcedureStore()
    report = ingest_procedures([DOC], store, FakeEmbedder())
    assert report.ingested == ("PO-FICT-900",)
    vectors = store.embeddings["PO-FICT-900"]
    assert vectors is not None and len(vectors) == 2
    assert all(len(v) == 1536 for v in vectors)


def test_second_run_skips_unchanged():
    store = InMemoryProcedureStore()
    ingest_procedures([DOC], store, FakeEmbedder())
    report = ingest_procedures([DOC], store, FakeEmbedder())
    assert report.ingested == () and report.unchanged == ("PO-FICT-900",)


def test_changed_text_is_reingested():
    store = InMemoryProcedureStore()
    ingest_procedures([DOC], store, FakeEmbedder())
    report = ingest_procedures([DOC.replace("Passo um", "Passo dois")], store, FakeEmbedder())
    assert report.ingested == ("PO-FICT-900",)


def test_switching_embedding_mode_reingests():
    store = InMemoryProcedureStore()
    ingest_procedures([DOC], store, None)
    assert store.embeddings["PO-FICT-900"] is None
    report = ingest_procedures([DOC], store, FakeEmbedder())
    assert report.ingested == ("PO-FICT-900",)


def test_fake_embedder_is_deterministic_and_normalized():
    a, b = FakeEmbedder().embed(["x", "x"])
    assert a == b
    assert abs(sum(v * v for v in a) - 1.0) < 1e-6
