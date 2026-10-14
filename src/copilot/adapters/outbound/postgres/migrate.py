"""Applies numbered SQL files from MIGRATIONS_DIR, in order, once each."""

from pathlib import Path

import psycopg

from copilot.config import Settings

_LOCK_ID = 7_340_001


def apply_migrations(database_url: str, migrations_dir: Path) -> list[str]:
    applied_now: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            done = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
            for path in sorted(migrations_dir.glob("*.sql")):
                if path.name in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
                    )
                applied_now.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
    return applied_now


def main() -> None:
    settings = Settings()
    applied = apply_migrations(settings.database_url, Path(settings.migrations_dir))
    print("applied:", ", ".join(applied) if applied else "nothing to do")


if __name__ == "__main__":
    main()
