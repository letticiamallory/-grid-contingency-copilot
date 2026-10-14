import json
import re

from copilot.application.ports import LLMResponse

_CHUNK = re.compile(r"\[chunk_id=([^\]]+)\] \([^)]*\)\n(.+)")


class EchoLLM:
    """Deterministic stand-in: cites the first line of the best-ranked chunk it was shown.
    Useful for API tests and for the pipeline-only evaluation; it has no language ability."""

    model = "echo-llm"

    def complete(self, system: str, user: str) -> LLMResponse:
        match = _CHUNK.search(user)
        if not match:
            return LLMResponse(json.dumps({"refusal": "sem trechos", "steps": []}), self.model)
        chunk_id, first_line = match.group(1), match.group(2).strip()
        step = {
            "instruction": first_line,
            "citations": [{"chunk_id": chunk_id, "quote": first_line}],
        }
        return LLMResponse(json.dumps({"refusal": None, "steps": [step]}), self.model)


class FakeLLM:
    """Scripted responses, returned in order. An Exception item is raised instead of returned."""

    def __init__(self, responses: list[str | Exception], model: str = "fake-llm") -> None:
        self._responses = list(responses)
        self._model = model
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> LLMResponse:
        self.calls.append((system, user))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(text=item, model=self._model)
