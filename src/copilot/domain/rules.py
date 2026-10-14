from copilot.domain import models
from copilot.domain.errors import JustificationRequired, SuggestionNotPending

APPROVE = "approve"
REJECT = "reject"


def decide(status: str, outcome: str, justification: str | None) -> str:
    """Returns the new suggestion status. Only a pending suggestion can be decided, and only a
    human decision (this function is the sole way to reach approved/rejected) moves it."""
    if status != models.PENDING_REVIEW:
        raise SuggestionNotPending(f"a sugestao esta '{status}' e nao aceita decisao")
    if outcome == APPROVE:
        return models.APPROVED
    if outcome == REJECT:
        if not justification or not justification.strip():
            raise JustificationRequired("rejeitar exige uma justificativa")
        return models.REJECTED
    raise ValueError(f"unknown outcome: {outcome!r}")
