from copilot.domain.procedures import Procedure


class InMemoryProcedureStore:
    def __init__(self) -> None:
        self.procedures: dict[str, Procedure] = {}
        self.embeddings: dict[str, list[list[float]] | None] = {}
        self._models: dict[str, str | None] = {}

    def ingestion_state(self) -> dict[str, tuple[str, str | None]]:
        return {c: (p.content_hash, self._models[c]) for c, p in self.procedures.items()}

    def replace_procedure(
        self,
        procedure: Procedure,
        embeddings: list[list[float]] | None,
        embedding_model: str | None,
    ) -> None:
        self.procedures[procedure.code] = procedure
        self.embeddings[procedure.code] = embeddings
        self._models[procedure.code] = embedding_model
