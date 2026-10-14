"""Evaluation scenarios (docs/03): YAML files, validated on load."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SPLITS = ("calibration", "test")
MIN_PER_CATEGORY = 2


class ScenarioError(ValueError):
    pass


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str
    split: str
    written_before_kb: bool
    event_type: str
    element: str
    occurred_at: datetime
    attributes: dict[str, Any]
    refusal: bool
    procedures: tuple[str, ...]
    required_topics: tuple[str, ...] = ()
    forbidden_steps: tuple[str, ...] = ()
    notes: str = ""
    author: str = "assistant-draft"


def _parse(raw: Any, source: str) -> Scenario:
    try:
        event, expected = raw["event"], raw["expected"]
        scenario = Scenario(
            id=str(raw["id"]),
            category=str(raw["category"]),
            split=str(raw["split"]),
            written_before_kb=bool(raw["written_before_kb"]),
            event_type=str(event["type"]),
            element=str(event["element"]),
            occurred_at=datetime.fromisoformat(str(event["occurred_at"])),
            attributes=dict(event.get("attributes") or {}),
            refusal=bool(expected["refusal"]),
            procedures=tuple(expected.get("procedures") or ()),
            required_topics=tuple(expected.get("required_topics") or ()),
            forbidden_steps=tuple(expected.get("forbidden_steps") or ()),
            notes=str(raw.get("notes", "")),
            author=str(raw.get("author", "assistant-draft")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ScenarioError(f"{source}: cenario malformado ({exc!r})") from exc
    if scenario.split not in SPLITS:
        raise ScenarioError(f"{source}: {scenario.id}: split invalido {scenario.split!r}")
    if scenario.refusal and scenario.procedures:
        raise ScenarioError(f"{source}: {scenario.id}: refusal=true exige procedures vazio")
    if not scenario.refusal and not scenario.procedures:
        raise ScenarioError(
            f"{source}: {scenario.id}: refusal=false exige ao menos um procedimento"
        )
    return scenario


def load_scenarios(directory: Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.yaml")):
        docs = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(docs, list):
            raise ScenarioError(f"{path.name}: esperado uma lista de cenarios")
        scenarios.extend(_parse(raw, path.name) for raw in docs)
    ids = Counter(s.id for s in scenarios)
    duplicated = sorted(i for i, n in ids.items() if n > 1)
    if duplicated:
        raise ScenarioError(f"ids duplicados: {duplicated}")
    return scenarios


def structural_problems(scenarios: list[Scenario]) -> list[str]:
    """Rules of docs/03 that concern the set as a whole (reported, not fatal while drafting)."""
    problems: list[str] = []
    per_category = Counter(s.category for s in scenarios)
    for category, n in sorted(per_category.items()):
        if n < MIN_PER_CATEGORY:
            problems.append(f"categoria {category} tem {n} cenario(s); minimo {MIN_PER_CATEGORY}")
    if not 60 <= len(scenarios) <= 90:
        problems.append(f"total de {len(scenarios)} cenarios; esperado entre 60 e 90")
    before_kb = sum(s.written_before_kb for s in scenarios)
    if scenarios and before_kb / len(scenarios) < 0.30:
        problems.append(
            f"written_before_kb em {before_kb}/{len(scenarios)} cenarios; esperado >= 30% (ADR-008)"
        )
    return problems
