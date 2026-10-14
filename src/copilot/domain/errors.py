class DomainError(Exception):
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EventNotFound(DomainError):
    code = "event_not_found"


class SuggestionNotFound(DomainError):
    code = "suggestion_not_found"


class SuggestionNotPending(DomainError):
    code = "suggestion_not_pending"


class JustificationRequired(DomainError):
    code = "justification_required"


class LLMUnavailable(DomainError):
    code = "llm_unavailable"
