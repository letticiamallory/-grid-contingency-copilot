import psycopg

from copilot.application.use_cases.ingest_procedures import IngestConflictError
from copilot.domain.procedures import Procedure


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


class PostgresProcedureStore:
    """Uses the caller's connection and does not commit; the caller owns the transaction."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def ingestion_state(self) -> dict[str, tuple[str, str | None]]:
        rows = self._conn.execute("SELECT code, content_hash, embedding_model FROM procedures")
        return {code: (h, model) for code, h, model in rows}

    def replace_procedure(
        self,
        procedure: Procedure,
        embeddings: list[list[float]] | None,
        embedding_model: str | None,
    ) -> None:
        try:
            with self._conn.transaction():
                self._upsert(procedure, embedding_model)
                self._conn.execute(
                    "DELETE FROM chunks WHERE procedure_code = %s", (procedure.code,)
                )
                self._insert_chunks(procedure, embeddings)
        except psycopg.errors.ForeignKeyViolation as exc:
            raise IngestConflictError(
                f"{procedure.code} mudou, mas trechos antigos dele ja foram citados em "
                "sugestoes. Publique como nova versao em vez de editar a existente."
            ) from exc

    def _upsert(self, procedure: Procedure, embedding_model: str | None) -> None:
        self._conn.execute(
            "INSERT INTO procedures (code, title, version, status, content_hash,"
            " embedding_model, applies_to)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (code) DO UPDATE SET title = EXCLUDED.title,"
            " version = EXCLUDED.version, status = EXCLUDED.status,"
            " content_hash = EXCLUDED.content_hash,"
            " embedding_model = EXCLUDED.embedding_model,"
            " applies_to = EXCLUDED.applies_to, ingested_at = now()",
            (
                procedure.code,
                procedure.title,
                procedure.version,
                procedure.status,
                procedure.content_hash,
                embedding_model,
                list(procedure.applies_to),
            ),
        )

    def _insert_chunks(self, procedure: Procedure, embeddings: list[list[float]] | None) -> None:
        for i, chunk in enumerate(procedure.chunks):
            vector = vector_literal(embeddings[i]) if embeddings else None
            self._conn.execute(
                "INSERT INTO chunks (procedure_code, section, text, embedding)"
                " VALUES (%s, %s, %s, %s::vector)",
                (procedure.code, chunk.section, chunk.text, vector),
            )
