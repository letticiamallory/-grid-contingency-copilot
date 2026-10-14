"""Composition root: the only place that knows the concrete implementations.

Run: uv run uvicorn copilot.main:app
"""

from pathlib import Path

import psycopg

from copilot.adapters.inbound.http.app import AppDeps, create_app
from copilot.adapters.outbound.llm.openrouter_embedder import OpenRouterEmbedder
from copilot.adapters.outbound.llm.openrouter_llm import OpenRouterLLM
from copilot.adapters.outbound.llm.resilient import FallbackLLM
from copilot.adapters.outbound.llm.unconfigured import UnconfiguredLLM
from copilot.application.ports import EmbedderPort, LLMPort
from copilot.config import Settings
from copilot.evaluation.runner import load_threshold


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


def refusal_threshold(settings: Settings, hybrid: bool) -> float:
    """The calibrated threshold of the retriever in use (scales differ). Fails at startup if the
    file is missing: silently using 0.0 would answer events the base knows nothing about."""
    path = Path(settings.thresholds_dir) / f"threshold-{'hybrid' if hybrid else 'lexical'}.json"
    if not path.exists():
        raise RuntimeError(
            f"limiar de recusa calibrado nao encontrado: {path} (make eval-calibrate)"
        )
    return load_threshold(path)


settings = Settings()
_embedder = build_embedder(settings)

app = create_app(
    AppDeps(
        connect=lambda: psycopg.connect(settings.database_url, connect_timeout=5),
        llm=build_llm(settings),
        embedder=_embedder,
        min_score=refusal_threshold(settings, hybrid=_embedder is not None),
    )
)
