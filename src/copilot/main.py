"""Composition root: the only place that knows the concrete implementations.

Run: uv run uvicorn copilot.main:app
"""

import psycopg

from copilot.adapters.inbound.http.app import AppDeps, create_app
from copilot.adapters.outbound.llm.openrouter_embedder import OpenRouterEmbedder
from copilot.adapters.outbound.llm.openrouter_llm import OpenRouterLLM
from copilot.adapters.outbound.llm.resilient import FallbackLLM
from copilot.adapters.outbound.llm.unconfigured import UnconfiguredLLM
from copilot.application.ports import EmbedderPort, LLMPort
from copilot.config import Settings


def build_llm(settings: Settings) -> LLMPort:
    """Without an API key and a model the API answers 503 llm_unavailable instead of faking."""
    if not settings.openrouter_api_key or not settings.llm_model:
        return UnconfiguredLLM()
    names = [settings.llm_model]
    if settings.llm_fallback_model:
        names.append(settings.llm_fallback_model)
    return FallbackLLM([OpenRouterLLM(settings.openrouter_api_key, n) for n in names])


def build_embedder(settings: Settings) -> EmbedderPort | None:
    """Without a key the API retrieves lexically only."""
    if not settings.openrouter_api_key:
        return None
    return OpenRouterEmbedder(settings.openrouter_api_key, settings.embedding_model)


settings = Settings()

app = create_app(
    AppDeps(
        connect=lambda: psycopg.connect(settings.database_url, connect_timeout=5),
        llm=build_llm(settings),
        embedder=build_embedder(settings),
    )
)
