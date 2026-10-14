from datetime import UTC, datetime, timedelta, timezone

import pytest

from copilot.adapters.outbound.postgres.audit import canonical, compute_hash, first_broken_seq
from copilot.domain import models, rules
from copilot.domain.errors import JustificationRequired, SuggestionNotPending

AT = datetime(2026, 3, 14, 5, 41, tzinfo=UTC)


def _chain(n: int):
    rows, prev = [], ""
    for i in range(n):
        payload = {"i": i, "score": 1.5}
        h = compute_hash(prev, "e1", "KIND", AT + timedelta(seconds=i), payload)
        rows.append((i + 1, "KIND", AT + timedelta(seconds=i), payload, prev, h))
        prev = h
    return rows


def test_intact_chain_has_no_broken_link():
    assert first_broken_seq("e1", _chain(4)) is None
    assert first_broken_seq("e1", []) is None


def test_edited_payload_is_detected_at_that_row():
    rows = _chain(4)
    seq, kind, at, payload, prev, h = rows[1]
    rows[1] = (seq, kind, at, {**payload, "i": 99}, prev, h)
    assert first_broken_seq("e1", rows) == 2


def test_removed_row_is_detected():
    rows = _chain(4)
    del rows[1]
    assert first_broken_seq("e1", rows) == 3


def test_reordered_rows_are_detected():
    rows = _chain(3)
    rows[0], rows[1] = rows[1], rows[0]
    assert first_broken_seq("e1", rows) is not None


def test_hash_is_independent_of_timezone_representation_and_key_order():
    brt = timezone(timedelta(hours=-3))
    a = compute_hash("p", "e", "K", AT, {"a": 1, "b": 2})
    b = compute_hash("p", "e", "K", AT.astimezone(brt), {"b": 2, "a": 1})
    assert a == b
    assert canonical({"b": 1, "a": "é"}) == '{"a":"é","b":1}'


def test_approve_and_reject_from_pending():
    assert rules.decide(models.PENDING_REVIEW, "approve", None) == models.APPROVED
    assert rules.decide(models.PENDING_REVIEW, "reject", "motivo") == models.REJECTED


@pytest.mark.parametrize("justification", [None, "", "   "])
def test_reject_needs_a_real_justification(justification):
    with pytest.raises(JustificationRequired):
        rules.decide(models.PENDING_REVIEW, "reject", justification)


@pytest.mark.parametrize("status", [models.REFUSED, models.APPROVED, models.REJECTED])
def test_only_pending_can_be_decided(status):
    with pytest.raises(SuggestionNotPending):
        rules.decide(status, "approve", None)
