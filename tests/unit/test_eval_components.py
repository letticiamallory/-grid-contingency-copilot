import json
from datetime import UTC, datetime

import httpx

from copilot.adapters.outbound.fakes.audit import InMemoryAudit
from copilot.adapters.outbound.fakes.llm import FakeLLM
from copilot.adapters.outbound.llm.cached import CachedLLM
from copilot.adapters.outbound.llm.openrouter_llm import OpenRouterLLM
from copilot.application.ports import CatalogEntry, LLMResponse
from copilot.application.use_cases.generate_without_retrieval import GenerateWithoutRetrieval
from copilot.domain import models
from copilot.domain.models import Event
from copilot.domain.procedures import RetrievedChunk
from copilot.evaluation import metrics as m
from copilot.evaluation.metrics import ScenarioResult

CHUNK = RetrievedChunk(
    "c1", "PO-FICT-001", "1.0", "4.1", "1. Confirmar a posição dos disjuntores.", 0
)
EVENT = Event("e1", "t", "el", datetime(2026, 3, 14, tzinfo=UTC), {}, "tester")


class Catalog:
    def valid_procedures(self):
        return [CatalogEntry("PO-FICT-001", "1.0", "Linha desligada")]

    def chunks_of(self, code):
        return [CHUNK] if code == "PO-FICT-001" else []


def run(reply):
    audit = InMemoryAudit()
    llm = FakeLLM([json.dumps(reply)])
    return GenerateWithoutRetrieval(Catalog(), llm, audit).execute(EVENT), llm


def step(code="PO-FICT-001", quote="Confirmar a posição dos disjuntores"):
    return {"instruction": "Confirmar.", "citations": [{"procedure_code": code, "quote": quote}]}


def test_norag_prompt_has_titles_but_no_procedure_text():
    _, llm = run({"refusal": "x", "steps": []})
    user = llm.calls[0][1]
    assert "PO-FICT-001 v1.0: Linha desligada" in user
    assert "disjuntores" not in user


def test_norag_accepts_a_quote_that_really_exists_in_the_cited_procedure():
    s, _ = run({"refusal": None, "steps": [step()]})
    assert s.status == models.PENDING_REVIEW and s.steps[0].citations[0].chunk_id == "c1"


def test_norag_drops_invented_quotes_and_unknown_procedures():
    s, _ = run({"refusal": None, "steps": [step(quote="texto que o modelo inventou aqui")]})
    assert (s.status, s.refusal_reason) == (models.REFUSED, models.NO_VALID_CITATION)
    s, _ = run({"refusal": None, "steps": [step(code="PO-FICT-999")]})
    assert s.refusal_reason == models.NO_VALID_CITATION


def test_norag_model_refusal_is_model_declined():
    s, _ = run({"refusal": "nao conheco o texto", "steps": []})
    assert s.refusal_reason == models.MODEL_DECLINED


class Scripted:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0

    def complete(self, system, user):
        self.calls += 1
        return self.responses.pop(0)


def test_cache_serves_identical_calls_and_separates_repetitions(tmp_path):
    inner = Scripted([LLMResponse("a", "m", 10, 5, 0.01, 1.5), LLMResponse("b", "m")])
    r1 = CachedLLM(inner, "m", tmp_path, salt="0").complete("s", "u")
    again = CachedLLM(inner, "m", tmp_path, salt="0").complete("s", "u")
    assert again == r1 and again.cost_usd == 0.01 and again.latency_s == 1.5
    other_rep = CachedLLM(inner, "m", tmp_path, salt="1").complete("s", "u")
    assert inner.calls == 2 and other_rep.text == "b"


def test_openrouter_adapter_reads_usage_and_cost():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.0003},
            },
        )

    llm = OpenRouterLLM("k", "m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    r = llm.complete("s", "u")
    assert (r.prompt_tokens, r.completion_tokens, r.cost_usd) == (100, 20, 0.0003)
    assert r.latency_s is not None and r.latency_s >= 0


def result(scenario_id, rep, recalled):
    return ScenarioResult(
        scenario_id, "C", "test", False, ("P",), ("P",) if recalled else ("X",), 1.0, False,
        None, 1, 0, False, (), (), repetition=rep,
    )  # fmt: skip


def test_bootstrap_resamples_scenarios_not_repetitions():
    # 2 scenarios x 3 repetitions: one always recalled, one never. A per-row bootstrap would
    # give a CI narrower than the scenario-level one (which must span 0 and 1).
    rs = [result("A", r, True) for r in range(3)] + [result("B", r, False) for r in range(3)]
    stat = lambda xs: m.mean([m.recall_at_k(r) for r in xs])  # noqa: E731
    low, high = m.bootstrap_ci(rs, stat, seed=3)
    assert (low, high) == (0.0, 1.0)


def test_recall_is_undefined_without_retrieval():
    r = ScenarioResult(
        "A", "C", "test", False, ("P",), (), None, True, None, 0, 0, False, (), (),
        retrieval_used=False,
    )  # fmt: skip
    assert m.recall_at_k(r) is None and m.reciprocal_rank(r) is None
