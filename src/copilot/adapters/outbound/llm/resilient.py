import time
from collections.abc import Callable, Sequence

from copilot.adapters.outbound.llm.openrouter_llm import LLMCallError
from copilot.application.ports import LLMPort, LLMResponse
from copilot.domain.errors import LLMUnavailable


class CircuitBreaker:
    """Opens after `threshold` consecutive failures and stays open for `open_for_s`; then lets
    one trial call through (half-open). A success closes it; a failed trial reopens it."""

    def __init__(
        self,
        threshold: int = 3,
        open_for_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = threshold
        self._open_for_s = open_for_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if self._clock() - self._opened_at >= self._open_for_s:
            # Half-open: allow one trial; push the window forward so concurrent callers wait.
            self._opened_at = self._clock()
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = self._clock()


class FallbackLLM:
    """Tries models in order, each behind its own circuit breaker. The model that actually
    answered is in the response. If all fail, raises LLMUnavailable: never degrades to an
    answer without a model (ADR-005)."""

    def __init__(
        self,
        models: Sequence[LLMPort],
        breaker_factory: Callable[[], CircuitBreaker] = CircuitBreaker,
    ) -> None:
        if not models:
            raise ValueError("at least one model is required")
        self._entries = [(m, breaker_factory()) for m in models]

    def complete(self, system: str, user: str) -> LLMResponse:
        for llm, breaker in self._entries:
            if not breaker.allow():
                continue
            try:
                response = llm.complete(system, user)
            except LLMCallError:
                breaker.record_failure()
                continue
            breaker.record_success()
            return response
        raise LLMUnavailable("todos os modelos falharam ou estao com o circuito aberto")
