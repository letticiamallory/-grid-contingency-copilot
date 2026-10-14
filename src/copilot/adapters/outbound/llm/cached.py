import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from copilot.application.ports import LLMPort, LLMResponse


class CachedLLM:
    """Disk cache keyed by (model, salt, system, user), for repeating evaluation runs at no cost.
    `salt` separates repetitions: at temperature 0 repetitions are otherwise served identically.
    Cached responses keep the usage and latency of the original call."""

    def __init__(self, inner: LLMPort, model: str, directory: Path, salt: str = "0") -> None:
        self._inner = inner
        self._model = model
        self._dir = directory
        self._salt = salt
        self.hits = 0

    def complete(self, system: str, user: str) -> LLMResponse:
        key = hashlib.sha256(
            json.dumps([self._model, self._salt, system, user], ensure_ascii=False).encode()
        ).hexdigest()
        path = self._dir / f"{key}.json"
        if path.exists():
            self.hits += 1
            return LLMResponse(**json.loads(path.read_text(encoding="utf-8")))
        response = self._inner.complete(system, user)
        self._dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(response), ensure_ascii=False), encoding="utf-8")
        return response
