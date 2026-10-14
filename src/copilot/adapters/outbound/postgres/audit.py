"""Append-only audit log with a per-event SHA-256 hash chain (ADR-006).

Detects tampering with stored rows; it does not stop someone with database superuser rights from
rewriting the whole chain.
"""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from copilot.application.ports import AuditEntry


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(
    prev_hash: str, event_id: str, kind: str, at: datetime, payload: dict[str, Any]
) -> str:
    stamp = at.astimezone(UTC).isoformat()
    material = f"{prev_hash}|{event_id}|{kind}|{stamp}|{canonical(payload)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def first_broken_seq(
    event_id: str, rows: list[tuple[int, str, datetime, dict[str, Any], str, str]]
) -> int | None:
    """rows: (seq, kind, at, payload, prev_hash, hash) in order. Returns the first seq whose link
    or hash does not check out, or None if the chain is intact."""
    expected_prev = ""
    for seq, kind, at, payload, prev_hash, stored_hash in rows:
        if prev_hash != expected_prev:
            return seq
        if compute_hash(prev_hash, event_id, kind, at, payload) != stored_hash:
            return seq
        expected_prev = stored_hash
    return None


class PostgresAudit:
    """Uses the caller's connection and transaction (no commit here)."""

    def __init__(
        self,
        conn: psycopg.Connection,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._conn = conn
        self._clock = clock

    def append(self, event_id: str, kind: str, payload: dict[str, Any]) -> None:
        # Serializes writers of the same event so the chain order is deterministic.
        self._conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (event_id,))
        row = self._conn.execute(
            "SELECT hash FROM audit_log WHERE event_id = %s ORDER BY seq DESC LIMIT 1",
            (event_id,),
        ).fetchone()
        prev_hash = row[0] if row else ""
        at = self._clock()
        self._conn.execute(
            "INSERT INTO audit_log (event_id, kind, payload, prev_hash, hash, at)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (
                event_id,
                kind,
                Jsonb(payload),
                prev_hash,
                compute_hash(prev_hash, event_id, kind, at, payload),
                at,
            ),
        )

    def trail(self, event_id: str) -> tuple[list[AuditEntry], bool]:
        rows = self._rows(event_id)
        entries = [AuditEntry(seq=r[0], kind=r[1], at=r[2], payload=r[3], hash=r[5]) for r in rows]
        return entries, first_broken_seq(event_id, rows) is None

    def verify(self, event_id: str) -> int | None:
        return first_broken_seq(event_id, self._rows(event_id))

    def event_ids(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT event_id FROM audit_log ORDER BY 1")
        return [str(r[0]) for r in rows]

    def _rows(self, event_id: str) -> list[tuple[int, str, datetime, dict[str, Any], str, str]]:
        cur = self._conn.execute(
            "SELECT seq, kind, at, payload, prev_hash, hash FROM audit_log"
            " WHERE event_id = %s ORDER BY seq",
            (event_id,),
        )
        return [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in cur]
