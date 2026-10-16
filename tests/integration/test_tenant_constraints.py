from __future__ import annotations

import os
import subprocess
import sys
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.fixture(scope="module")
def migrated_database():
    if not DATABASE_URL:
        pytest.skip("Set TEST_DATABASE_URL to run tenant constraint integration tests")
    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    subprocess.run(
        [sys.executable, "scripts/migrate.py"],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    return DATABASE_URL


def test_database_rejects_cross_tenant_conversation_channel(migrated_database):
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(migrated_database) as conn:
            conn.execute(
                "INSERT INTO tenants (id, name, slug) VALUES (%s::uuid, %s, %s), (%s::uuid, %s, %s)",
                (
                    tenant_a, "Tenant A", f"tenant-a-{tenant_a}",
                    tenant_b, "Tenant B", f"tenant-b-{tenant_b}",
                ),
            )
            channel_id = conn.execute(
                """INSERT INTO channels (tenant_id, provider, external_account_id)
                VALUES (%s::uuid, 'telegram', %s) RETURNING id""",
                (tenant_b, f"channel-{tenant_b}"),
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO conversations
                (tenant_id, channel_id, external_sender_id)
                VALUES (%s::uuid, %s::uuid, 'cross-tenant-test')""",
                (tenant_a, str(channel_id)),
            )
