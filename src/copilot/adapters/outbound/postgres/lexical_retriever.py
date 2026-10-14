import re

import psycopg

from copilot.domain.procedures import RetrievedChunk

# Candidates: chunks matching the text OR belonging to a procedure whose applies_to contains the
# event type. The type match adds a fixed boost of 1.0 on top of ts_rank (which is well below 1).
_SQL = """
SELECT c.id, c.procedure_code, p.version, c.section, c.text,
       COALESCE(ts_rank(c.tsv, q.query), 0)
         + CASE WHEN %(type)s::text IS NOT NULL AND p.applies_to @> ARRAY[%(type)s::text]
                THEN 1.0 ELSE 0 END AS score
FROM chunks c
JOIN procedures p ON p.code = c.procedure_code,
     (SELECT websearch_to_tsquery('portuguese', %(terms)s) AS query) q
WHERE p.status = 'vigente'
  AND (c.tsv @@ q.query
       OR (%(type)s::text IS NOT NULL AND p.applies_to @> ARRAY[%(type)s::text]))
ORDER BY score DESC, c.id
LIMIT %(k)s
"""


def or_query(text: str) -> str:
    """Any-word match: websearch_to_tsquery treats bare words as AND, which is too strict for
    free text."""
    return " or ".join(re.findall(r"\w+", text))


class LexicalRetriever:
    """Full-text search over chunks of valid ('vigente') procedures only."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def search(self, query: str, k: int, event_type: str | None = None) -> list[RetrievedChunk]:
        terms = or_query(query)
        if not terms and event_type is None:
            return []
        rows = self._conn.execute(_SQL, {"terms": terms, "type": event_type, "k": k}).fetchall()
        return [RetrievedChunk(str(r[0]), r[1], r[2], r[3], r[4], float(r[5])) for r in rows]
