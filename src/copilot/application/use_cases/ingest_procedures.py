from collections.abc import Iterable
from dataclasses import dataclass

from copilot.application.ports import EmbedderPort, ProcedureStore
from copilot.domain.procedures import parse_procedure


class IngestConflictError(RuntimeError):
    """A changed procedure cannot replace chunks that past suggestions already cite."""


@dataclass(frozen=True)
class IngestReport:
    ingested: tuple[str, ...]
    unchanged: tuple[str, ...]


def ingest_procedures(
    documents: Iterable[str],
    store: ProcedureStore,
    embedder: EmbedderPort | None,
) -> IngestReport:
    """Stores procedures and their chunks. Unchanged ones (same hash and embedding model) are
    skipped. Procedures that disappeared from the input are NOT removed."""
    state = store.ingestion_state()
    wanted_model = embedder.model if embedder else None
    ingested: list[str] = []
    unchanged: list[str] = []
    for raw in documents:
        procedure = parse_procedure(raw)
        if state.get(procedure.code) == (procedure.content_hash, wanted_model):
            unchanged.append(procedure.code)
            continue
        embeddings = None
        if embedder:
            embeddings = embedder.embed([c.text for c in procedure.chunks])
            if len(embeddings) != len(procedure.chunks):
                raise RuntimeError(
                    f"embedder returned {len(embeddings)} vectors for {procedure.code}"
                )
        store.replace_procedure(procedure, embeddings, wanted_model)
        ingested.append(procedure.code)
    return IngestReport(ingested=tuple(ingested), unchanged=tuple(unchanged))
