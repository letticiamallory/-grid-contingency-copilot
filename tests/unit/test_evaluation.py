from datetime import UTC, datetime
from pathlib import Path

import pytest

from copilot.adapters.outbound.fakes.llm import EchoLLM
from copilot.adapters.outbound.fakes.retriever import StubRetriever
from copilot.domain.procedures import RetrievedChunk
from copilot.evaluation import metrics as m
from copilot.evaluation.metrics import ScenarioResult
from copilot.evaluation.runner import calibrate_threshold, run_scenario
from copilot.evaluation.scenarios import (
    Scenario,
    ScenarioError,
    load_scenarios,
    structural_problems,
)

SCENARIO_DIR = Path(__file__).parents[2] / "eval" / "scenarios"


def result(**over) -> ScenarioResult:
    base = dict(
        scenario_id="S",
        category="C",
        split="test",
        expected_refusal=False,
        expected_procedures=("PO-FICT-001",),
        retrieved_procedures=("PO-FICT-002", "PO-FICT-001"),
        top_score=1.5,
        refused=False,
        refusal_reason=None,
        steps_kept=1,
        steps_dropped=0,
        format_error=False,
        accepted_steps=(("Confirmar disjuntores", ("PO-FICT-001",)),),
        forbidden_steps=(),
    )
    base.update(over)
    return ScenarioResult(**base)


def test_shipped_scenarios_load_and_are_well_formed():
    scenarios = load_scenarios(SCENARIO_DIR)
    assert len(scenarios) >= 60
    assert {s.split for s in scenarios} == {"calibration", "test"}
    refusals = [s for s in scenarios if s.refusal]
    assert refusals and all(not s.procedures for s in refusals)
    other_problems = [p for p in structural_problems(scenarios) if "written_before_kb" not in p]
    assert other_problems == []


def test_refusal_with_procedures_is_rejected(tmp_path):
    (tmp_path / "x.yaml").write_text(
        "- id: A\n  category: C\n  split: test\n  written_before_kb: false\n"
        "  event: {type: t, element: e, occurred_at: '2026-03-14T02:41:00-03:00'}\n"
        "  expected: {refusal: true, procedures: [PO-FICT-001]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ScenarioError, match="refusal=true"):
        load_scenarios(tmp_path)


def test_duplicate_ids_are_rejected(tmp_path):
    one = (
        "- id: A\n  category: C\n  split: test\n  written_before_kb: false\n"
        "  event: {type: t, element: e, occurred_at: '2026-03-14T02:41:00-03:00'}\n"
        "  expected: {refusal: true}\n"
    )
    (tmp_path / "a.yaml").write_text(one, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(one, encoding="utf-8")
    with pytest.raises(ScenarioError, match="duplicados"):
        load_scenarios(tmp_path)


def test_recall_and_mrr_use_first_expected_procedure():
    r = result()
    assert m.recall_at_k(r) == 1.0 and m.reciprocal_rank(r) == 0.5
    miss = result(retrieved_procedures=("PO-FICT-009",))
    assert m.recall_at_k(miss) == 0.0 and m.reciprocal_rank(miss) == 0.0


def test_retrieval_metrics_are_undefined_for_refusal_scenarios():
    r = result(expected_refusal=True, expected_procedures=())
    assert m.recall_at_k(r) is None and m.reciprocal_rank(r) is None


def test_hallucination_counts_forbidden_and_off_procedure_steps():
    r = result(
        forbidden_steps=("religar a linha imediatamente",),
        accepted_steps=(
            ("Confirmar disjuntores", ("PO-FICT-001",)),
            ("Religar a linha imediatamente", ("PO-FICT-001",)),
            ("Outra coisa", ("PO-FICT-009",)),
        ),
    )
    assert m.hallucinated_steps(r) == (2, 3)


def test_any_accepted_step_in_a_refusal_scenario_is_hallucinated():
    r = result(expected_refusal=True, expected_procedures=())
    assert m.hallucinated_steps(r) == (1, 1)


def test_refusal_precision_and_recall():
    rs = [
        result(refused=True, expected_refusal=True),
        result(refused=True, expected_refusal=False),
        result(refused=False, expected_refusal=True),
    ]
    precision, recall = m.refusal_precision_recall(rs)
    assert precision == 0.5 and recall == 0.5


def test_bootstrap_ci_is_deterministic_and_brackets_the_value():
    rs = [result(retrieved_procedures=("PO-FICT-001",) if i % 2 else ("X",)) for i in range(20)]
    stat = lambda xs: m.mean([m.recall_at_k(r) for r in xs])  # noqa: E731
    ci = m.bootstrap_ci(rs, stat, seed=1)
    assert ci == m.bootstrap_ci(rs, stat, seed=1)
    assert ci is not None and ci[0] <= 0.5 <= ci[1]


def test_calibration_picks_the_middle_of_the_optimal_range():
    rs = [
        result(top_score=0.02, expected_refusal=True, expected_procedures=()),
        result(top_score=0.05, expected_refusal=True, expected_procedures=()),
        result(top_score=1.2, expected_refusal=False),
        result(top_score=1.4, expected_refusal=False),
    ]
    threshold, accuracy = calibrate_threshold(rs)
    assert accuracy == 1.0 and 0.05 < threshold <= 1.2


def test_calibration_counts_empty_retrieval_as_refusal():
    rs = [result(top_score=None, expected_refusal=True, expected_procedures=())]
    assert calibrate_threshold(rs)[1] == 1.0


CHUNK = RetrievedChunk(
    "c1", "PO-FICT-001", "1.0", "4.1", "1. Confirmar a posição dos disjuntores.", 1.4
)
SCENARIO = Scenario(
    id="S1",
    category="C01",
    split="test",
    written_before_kb=False,
    event_type="line_trip_by_protection",
    element="LT-FICT-230-04",
    occurred_at=datetime(2026, 3, 14, 2, 41, tzinfo=UTC),
    attributes={},
    refusal=False,
    procedures=("PO-FICT-001",),
)


def test_run_scenario_reports_retrieval_and_accepted_steps():
    r = run_scenario(SCENARIO, StubRetriever([CHUNK]), EchoLLM(), k=6, min_score=0.5)
    assert not r.refused and r.retrieved_procedures == ("PO-FICT-001",)
    assert r.steps_kept == 1 and r.accepted_steps[0][1] == ("PO-FICT-001",)


def test_run_scenario_refuses_below_threshold():
    r = run_scenario(SCENARIO, StubRetriever([CHUNK]), EchoLLM(), k=6, min_score=2.0)
    assert r.refused and r.refusal_reason == "no_applicable_procedure" and r.steps_kept == 0
