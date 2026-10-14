import psycopg

from copilot.application.ports import CatalogEntry
from copilot.domain.procedures import RetrievedChunk


class PostgresCatalog:
    """Valid ('vigente') procedures and their chunks; for the no-retrieval baseline only."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def valid_procedures(self) -> list[CatalogEntry]:
        rows = self._conn.execute(
            "SELECT code, version, title FROM procedures WHERE status = 'vigente' ORDER BY code"
        ).fetchall()
        return [CatalogEntry(*r) for r in rows]

    def chunks_of(self, procedure_code: str) -> list[RetrievedChunk]:
        rows = self._conn.execute(
            "SELECT c.id, c.procedure_code, p.version, c.section, c.text"
            " FROM chunks c JOIN procedures p ON p.code = c.procedure_code"
            " WHERE c.procedure_code = %s AND p.status = 'vigente' ORDER BY c.id",
            (procedure_code,),
        ).fetchall()
        return [RetrievedChunk(str(r[0]), r[1], r[2], r[3], r[4], 0.0) for r in rows]
