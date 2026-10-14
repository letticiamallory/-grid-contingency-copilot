from copilot.application.ports import LLMResponse
from copilot.domain.errors import LLMUnavailable


class UnconfiguredLLM:
    """Used until a real provider adapter exists/is configured: fails loudly, never fakes."""

    def complete(self, system: str, user: str) -> LLMResponse:
        raise LLMUnavailable("nenhum provedor de LLM configurado")
