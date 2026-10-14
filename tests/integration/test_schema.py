import psycopg
import pytest

from copilot.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
def conn():
    with psycopg.connect(Settings().database_url) as c:
        yield c
        c.rollback()


def _insert_event(conn: psycopg.Connection) -> str:
    row = conn.execute(
        "INSERT INTO events (type, element, occurred_at, reported_by) "
        "VALUES ('t', 'e', now(), 'tester') RETURNING id"
    ).fetchone()
    return str(row[0])


def test_audit_log_blocks_update_and_delete(conn):
    event_id = _insert_event(conn)
    conn.execute(
        "INSERT INTO audit_log (event_id, kind, payload, prev_hash, hash) "
        "VALUES (%s, 'EVENT_RECEIVED', '{}', '', 'h1')",
        (event_id,),
    )
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        conn.execute("UPDATE audit_log SET hash = 'x'")
    conn.rollback()


def test_refusal_reason_must_match_status(conn):
    event_id = _insert_event(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO suggestions (event_id, status) VALUES (%s, 'refused')", (event_id,)
        )
    conn.rollback()


def test_reject_requires_justification(conn):
    event_id = _insert_event(conn)
    sid = conn.execute(
        "INSERT INTO suggestions (event_id, status) VALUES (%s, 'pending_review') RETURNING id",
        (event_id,),
    ).fetchone()[0]
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO decisions (suggestion_id, outcome, decided_by) "
            "VALUES (%s, 'reject', 'tester')",
            (sid,),
        )
    conn.rollback()
