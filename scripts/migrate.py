"""Apply numbered PostgreSQL migrations exactly once, with a transaction per migration.

Usage:
    DATABASE_URL=postgresql://... python scripts/migrate.py

The SQL files are intentionally idempotent for fresh Docker bootstrap compatibility.
This runner adds an explicit ledger for existing environments; take a database backup
before running it against any database containing business data.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "database" / "migrations"
MIGRATION_NAME = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL is required.", file=sys.stderr)
        return 2

    files = sorted(
        path for path in MIGRATIONS_DIR.iterdir()
        if path.is_file() and MIGRATION_NAME.fullmatch(path.name)
    )
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )"""
        )
        applied_count = conn.execute(
            "SELECT count(*) FROM schema_migrations"
        ).fetchone()[0]
        if applied_count == 0:
            existing_schema = conn.execute(
                """SELECT to_regclass('public.tenants') IS NOT NULL
                    OR to_regclass('public.channels') IS NOT NULL
                    OR to_regclass('public.products') IS NOT NULL"""
            ).fetchone()[0]
            if existing_schema:
                raise RuntimeError(
                    "Existing application tables were found but schema_migrations is empty. "
                    "Refusing to apply all migrations blindly. Back up the database, verify "
                    "its schema against the migration history, then perform an explicit "
                    "baseline procedure documented in docs/DATABASE_MIGRATIONS.md."
                )
        for migration in files:
            with conn.transaction():
                applied = conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s",
                    (migration.name,),
                ).fetchone()
                if applied:
                    print(f"SKIP {migration.name}")
                    continue
                sql = migration.read_text(encoding="utf-8")
                conn.execute(sql, prepare=False)
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (migration.name,),
                )
                print(f"APPLIED {migration.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
