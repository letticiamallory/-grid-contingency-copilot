"""Composition root: the only place that knows the concrete implementations.

Run: uv run uvicorn copilot.main:app
"""

import psycopg

from copilot.adapters.inbound.http.app import AppDeps, create_app
from copilot.adapters.outbound.llm.unconfigured import UnconfiguredLLM
from copilot.config import Settings

settings = Settings()

app = create_app(
    AppDeps(
        connect=lambda: psycopg.connect(settings.database_url, connect_timeout=5),
        # No real LLM adapter yet (ADR-005 is pending): generating suggestions answers 503
        # llm_unavailable instead of pretending.
        llm=UnconfiguredLLM(),
    )
)
