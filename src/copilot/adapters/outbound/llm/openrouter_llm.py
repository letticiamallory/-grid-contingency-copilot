import time
from collections.abc import Callable

import httpx

from copilot.application.ports import LLMResponse

_BASE_URL = "https://openrouter.ai/api/v1"


class LLMCallError(RuntimeError):
    """A single model call failed (after its own retry)."""


class OpenRouterLLM:
    """Chat completion via POST {base_url}/chat/completions (OpenAI-compatible shape), JSON mode,
    temperature 0. Timeout and at most `retries` retries with backoff, only for timeouts, network
    errors and 5xx/429; never for other 4xx (ADR-005).

    Verified only against a simulated transport; not yet exercised against the real API.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_s: float = 20.0,
        retries: int = 1,
        backoff_s: float = 1.0,
        base_url: str = _BASE_URL,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._model = model
        self._retries = retries
        self._backoff_s = backoff_s
        self._url = f"{base_url}/chat/completions"
        self._client = client or httpx.Client(timeout=timeout_s)
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._sleep = sleep

    @property
    def model(self) -> str:
        return self._model

    def complete(self, system: str, user: str) -> LLMResponse:
        body = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        last: LLMCallError | None = None
        for attempt in range(self._retries + 1):
            if attempt:
                self._sleep(self._backoff_s * attempt)
            try:
                return self._once(body)
            except _Retryable as exc:
                last = LLMCallError(str(exc))
        assert last is not None
        raise last

    def _once(self, body: dict[str, object]) -> LLMResponse:
        started = time.perf_counter()
        try:
            response = self._client.post(self._url, headers=self._headers, json=body)
        except httpx.HTTPError as exc:
            raise _Retryable(f"{self._model}: request failed: {type(exc).__name__}") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise _Retryable(f"{self._model}: HTTP {response.status_code}")
        if response.status_code != 200:
            raise LLMCallError(f"{self._model}: HTTP {response.status_code}")
        try:
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMCallError(f"{self._model}: unexpected response shape") from exc
        if not isinstance(text, str):
            raise LLMCallError(f"{self._model}: empty or non-text content")
        usage = payload.get("usage") if isinstance(payload, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        return LLMResponse(
            text=text,
            model=self._model,
            prompt_tokens=_int(usage.get("prompt_tokens")),
            completion_tokens=_int(usage.get("completion_tokens")),
            cost_usd=_float(usage.get("cost")),
            latency_s=time.perf_counter() - started,
        )


class _Retryable(Exception):
    pass


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
