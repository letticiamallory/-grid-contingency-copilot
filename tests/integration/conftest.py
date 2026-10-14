from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from copilot.adapters.inbound.http.app import AppDeps, create_app
from copilot.adapters.outbound.postgres.procedure_store import PostgresProcedureStore
from copilot.application.ports import LLMPort
from copilot.application.use_cases.ingest_procedures import ingest_procedures
from copilot.config import Settings

KB = Path(__file__).resolve().parents[2] / "knowledge_base"


@pytest.fixture
def db() -> Iterator[psycopg.Connection]:
    """One connection for the whole test, always rolled back: the dev database stays untouched."""
    with psycopg.connect(Settings().database_url, connect_timeout=5) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def kb(db: psycopg.Connection) -> psycopg.Connection:
    docs = [p.read_text(encoding="utf-8") for p in sorted(KB.glob("PO-FICT-*.md"))]
    ingest_procedures(docs, PostgresProcedureStore(db), None)
    return db


@pytest.fixture
def make_client(kb: psycopg.Connection) -> Callable[[LLMPort], TestClient]:
    @contextmanager
    def shared() -> Iterator[psycopg.Connection]:
        # Each request is a savepoint: rolls back on error like a real per-request transaction.
        with kb.transaction():
            yield kb

    def build(llm: LLMPort) -> TestClient:
        return TestClient(create_app(AppDeps(connect=shared, llm=llm)))

    return build
