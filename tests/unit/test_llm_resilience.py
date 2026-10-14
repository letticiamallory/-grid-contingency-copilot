import httpx
import pytest

from copilot.adapters.outbound.llm.openrouter_llm import LLMCallError, OpenRouterLLM
from copilot.adapters.outbound.llm.resilient import CircuitBreaker, FallbackLLM
from copilot.application.ports import LLMResponse
from copilot.config import Settings
from copilot.domain.errors import LLMUnavailable
from copilot.main import build_llm


def ok(content="{}"):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def make(handler, **kw):
    sleeps: list[float] = []
    llm = OpenRouterLLM(
        "key",
        "prov/model-a",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
        **kw,
    )
    return llm, sleeps


def test_success_returns_text_and_model_and_sends_deterministic_json_request():
    seen = {}

    def handler(request):
        seen["body"] = request.read()
        seen["auth"] = request.headers["authorization"]
        return ok('{"steps": []}')

    llm, _ = make(handler)
    r = llm.complete("sys", "usr")
    assert (r.text, r.model) == ('{"steps": []}', "prov/model-a")
    assert seen["auth"] == "Bearer key"
    assert b'"temperature":0' in seen["body"].replace(b" ", b"")
    assert b"json_object" in seen["body"]


def test_5xx_is_retried_once_with_backoff_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else ok()

    llm, sleeps = make(handler)
    assert llm.complete("s", "u").text == "{}"
    assert len(calls) == 2 and sleeps == [1.0]


def test_gives_up_after_the_retry():
    llm, _ = make(lambda r: httpx.Response(500))
    with pytest.raises(LLMCallError, match="HTTP 500"):
        llm.complete("s", "u")


def test_timeout_is_retried_and_reported_without_details():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    llm, _ = make(handler)
    with pytest.raises(LLMCallError, match="ReadTimeout"):
        llm.complete("s", "u")
    assert len(calls) == 2


def test_4xx_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401)

    llm, _ = make(handler)
    with pytest.raises(LLMCallError, match="HTTP 401"):
        llm.complete("s", "u")
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{"message": {}}]}])
def test_unexpected_shape_is_an_error(payload):
    llm, _ = make(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(LLMCallError, match="unexpected"):
        llm.complete("s", "u")


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_breaker_opens_after_threshold_and_half_opens_after_the_window():
    clock = Clock()
    b = CircuitBreaker(threshold=3, open_for_s=30, clock=clock)
    for _ in range(3):
        assert b.allow()
        b.record_failure()
    assert not b.allow()
    clock.now = 31
    assert b.allow()  # trial
    assert not b.allow()  # only one trial per window
    b.record_success()
    assert b.allow()


def test_success_resets_the_failure_count():
    b = CircuitBreaker(threshold=2, clock=Clock())
    b.record_failure()
    b.record_success()
    b.record_failure()
    assert b.allow()


class Stub:
    def __init__(self, model, fail=False):
        self.model, self.fail, self.calls = model, fail, 0

    def complete(self, system, user):
        self.calls += 1
        if self.fail:
            raise LLMCallError("down")
        return LLMResponse("{}", self.model)


def test_fallback_uses_secondary_and_reports_the_model_that_answered():
    primary, secondary = Stub("a", fail=True), Stub("b")
    assert FallbackLLM([primary, secondary]).complete("s", "u").model == "b"


def test_open_breaker_skips_the_primary_without_calling_it():
    clock = Clock()
    primary, secondary = Stub("a", fail=True), Stub("b")
    llm = FallbackLLM([primary, secondary], lambda: CircuitBreaker(3, 30, clock))
    for _ in range(3):
        llm.complete("s", "u")
    assert primary.calls == 3
    llm.complete("s", "u")
    assert primary.calls == 3 and secondary.calls == 4


def test_all_models_failing_raises_llm_unavailable_never_a_fake_answer():
    with pytest.raises(LLMUnavailable):
        FallbackLLM([Stub("a", fail=True), Stub("b", fail=True)]).complete("s", "u")


def test_composition_without_key_or_model_stays_unconfigured():
    from copilot.adapters.outbound.llm.unconfigured import UnconfiguredLLM

    assert isinstance(build_llm(Settings(openrouter_api_key="", llm_model="x")), UnconfiguredLLM)
    assert isinstance(build_llm(Settings(openrouter_api_key="k", llm_model="")), UnconfiguredLLM)
    assert isinstance(build_llm(Settings(openrouter_api_key="k", llm_model="x")), FallbackLLM)
