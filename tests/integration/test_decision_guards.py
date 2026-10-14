"""Database-level guards of ADR-006, independent of the application code."""

import psycopg
import pytest

pytestmark = pytest.mark.integration


def _suggestion(db: psycopg.Connection, status: str = "pending_review") -> str:
    event_id = db.execute(
        "INSERT INTO events (type, element, occurred_at, reported_by)"
        " VALUES ('t', 'e', now(), 'tester') RETURNING id"
    ).fetchone()[0]
    reason = "'no_applicable_procedure'" if status == "refused" else "NULL"
    return str(
        db.execute(
            f"INSERT INTO suggestions (event_id, status, refusal_reason)"
            f" VALUES (%s, %s, {reason}) RETURNING id",
            (event_id, status),
        ).fetchone()[0]
    )


def test_cannot_decide_a_refused_suggestion(db):
    sid = _suggestion(db, "refused")
    with pytest.raises(psycopg.errors.CheckViolation, match="pending_review"):
        db.execute(
            "INSERT INTO decisions (suggestion_id, outcome, decided_by)"
            " VALUES (%s, 'approve', 'op')",
            (sid,),
        )


def test_approved_status_without_decision_is_rejected_at_commit_time(db):
    sid = _suggestion(db)
    db.execute("UPDATE suggestions SET status = 'approved' WHERE id = %s", (sid,))
    with pytest.raises(psycopg.errors.CheckViolation, match="human decision"):
        db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_status_cannot_be_approved_by_a_reject_decision(db):
    sid = _suggestion(db)
    db.execute(
        "INSERT INTO decisions (suggestion_id, outcome, justification, decided_by)"
        " VALUES (%s, 'reject', 'motivo', 'op')",
        (sid,),
    )
    db.execute("UPDATE suggestions SET status = 'approved' WHERE id = %s", (sid,))
    with pytest.raises(psycopg.errors.CheckViolation, match="matching human decision"):
        db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_decision_then_status_in_one_transaction_is_accepted(db):
    sid = _suggestion(db)
    db.execute(
        "INSERT INTO decisions (suggestion_id, outcome, decided_by) VALUES (%s, 'approve', 'op')",
        (sid,),
    )
    db.execute("UPDATE suggestions SET status = 'approved' WHERE id = %s", (sid,))
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")  # no error


def test_final_status_never_changes(db):
    sid = _suggestion(db)
    db.execute(
        "INSERT INTO decisions (suggestion_id, outcome, decided_by) VALUES (%s, 'approve', 'op')",
        (sid,),
    )
    db.execute("UPDATE suggestions SET status = 'approved' WHERE id = %s", (sid,))
    with pytest.raises(psycopg.errors.CheckViolation, match="final"):
        db.execute("UPDATE suggestions SET status = 'pending_review' WHERE id = %s", (sid,))


def test_pending_cannot_become_refused(db):
    sid = _suggestion(db)
    with pytest.raises(psycopg.errors.CheckViolation, match="refused"):
        db.execute("UPDATE suggestions SET status = 'refused' WHERE id = %s", (sid,))


def test_decisions_are_immutable(db):
    sid = _suggestion(db)
    db.execute(
        "INSERT INTO decisions (suggestion_id, outcome, decided_by) VALUES (%s, 'approve', 'op')",
        (sid,),
    )
    # Savepoints: a failed statement aborts the transaction, so isolate each attempt.
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"), db.transaction():
        db.execute("UPDATE decisions SET decided_by = 'outro' WHERE suggestion_id = %s", (sid,))
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"), db.transaction():
        db.execute("DELETE FROM decisions WHERE suggestion_id = %s", (sid,))
