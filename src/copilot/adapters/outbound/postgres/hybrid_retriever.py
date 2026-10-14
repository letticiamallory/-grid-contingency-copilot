import psycopg

from copilot.adapters.outbound.postgres.lexical_retriever import or_query
from copilot.adapters.outbound.postgres.procedure_store import vector_literal
from copilot.application.ports import EmbedderPort
from copilot.domain.errors import RetrievalUnavailable
from copilot.domain.procedures import RetrievedChunk

RRF_K = 60  # standard Reciprocal Rank Fusion constant
TYPE_BOOST = 1.0  # same boost as the lexical retriever, so thresholds keep a comparable shape
POOL = 30  # candidates taken from each ranking before fusion

_LEXICAL = """
SELECT c.id FROM chunks c JOIN procedures p ON p.code = c.procedure_code,
     (SELECT websearch_to_tsquery('portuguese', %(terms)s) AS query) q
WHERE p.status = 'vigente' AND c.tsv @@ q.query
ORDER BY ts_rank(c.tsv, q.query) DESC, c.id
LIMIT %(pool)s
"""

_VECTOR = """
SELECT c.id FROM chunks c JOIN procedures p ON p.code = c.procedure_code
WHERE p.status = 'vigente' AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> %(vec)s::vector, c.id
LIMIT %(pool)s
"""

_TYPED = """
SELECT c.id FROM chunks c JOIN procedures p ON p.code = c.procedure_code
WHERE p.status = 'vigente' AND p.applies_to @> ARRAY[%(type)s::text]
"""

_ROWS = """
SELECT c.id, c.procedure_code, p.version, c.section, c.text
FROM chunks c JOIN procedures p ON p.code = c.procedure_code
WHERE c.id = ANY(%(ids)s)
"""


class HybridRetriever:
    """Reciprocal Rank Fusion of full-text and vector rankings, plus the `applies_to` boost.

    Score = sum over rankings of 1/(RRF_K + rank) + TYPE_BOOST when the procedure applies to the
    event type. Scores of text/vector-only candidates stay below ~0.04, so a refusal threshold
    separates "covered by type" from "only similar in wording". Only chunks of valid procedures
    and with an embedding take part in the vector ranking. If the query cannot be embedded this
    raises RetrievalUnavailable instead of silently falling back to lexical-only results.
    """

    def __init__(self, conn: psycopg.Connection, embedder: EmbedderPort) -> None:
        self._conn = conn
        self._embedder = embedder

    def search(self, query: str, k: int, event_type: str | None = None) -> list[RetrievedChunk]:
        terms = or_query(query)
        try:
            vector = self._embedder.embed([query])[0] if query.strip() else None
        except Exception as exc:  # EmbeddingError and transport errors alike
            raise RetrievalUnavailable("falha ao gerar o embedding da consulta") from exc

        rankings: list[list[int]] = []
        if terms:
            rankings.append(self._ids(_LEXICAL, {"terms": terms, "pool": POOL}))
        if vector is not None:
            rankings.append(self._ids(_VECTOR, {"vec": vector_literal(vector), "pool": POOL}))
        typed = set(self._ids(_TYPED, {"type": event_type})) if event_type else set()

        scores: dict[int, float] = {}
        for ranking in rankings:
            for rank, chunk_id in enumerate(ranking, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank)
        for chunk_id in typed:
            scores[chunk_id] = scores.get(chunk_id, 0.0) + TYPE_BOOST
        if not scores:
            return []

        rows = {r[0]: r for r in self._conn.execute(_ROWS, {"ids": list(scores)}).fetchall()}
        top = sorted(scores, key=lambda cid: (-scores[cid], cid))[:k]
        return [
            RetrievedChunk(
                str(cid), rows[cid][1], rows[cid][2], rows[cid][3], rows[cid][4], scores[cid]
            )
            for cid in top
        ]

    def _ids(self, sql: str, params: dict[str, object]) -> list[int]:
        return [row[0] for row in self._conn.execute(sql, params).fetchall()]
