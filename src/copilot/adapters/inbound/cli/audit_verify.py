"""CLI: verifies the hash chain of every event's audit trail (make audit-verify)."""

import sys

import psycopg

from copilot.adapters.outbound.postgres.audit import PostgresAudit
from copilot.config import Settings


def main() -> int:
    with psycopg.connect(Settings().database_url, connect_timeout=5) as conn:
        audit = PostgresAudit(conn)
        event_ids = audit.event_ids()
        broken = [(e, seq) for e in event_ids if (seq := audit.verify(e)) is not None]
    for event_id, seq in broken:
        print(f"CADEIA ADULTERADA: evento {event_id}, primeira linha inconsistente seq={seq}")
    print(f"eventos verificados: {len(event_ids)}, com problema: {len(broken)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
