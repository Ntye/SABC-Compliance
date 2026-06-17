#!/usr/bin/env python3
"""One-shot SQLite → PostgreSQL data migration.

Run this ONCE after spinning up the postgres container the first time.
It is safe to re-run: any table that already contains rows in PostgreSQL
is skipped so you never overwrite existing data.

Usage (inside the backend container, or locally with pip deps installed):

    # Inside the running backend container:
    docker exec sabc-backend python /app/migrate_to_postgres.py

    # Or directly (set env vars first):
    DATABASE_URL=postgresql+asyncpg://sabc:secret@localhost:5432/sabc \
    DB_PATH=/path/to/platform.db \
    python migrate_to_postgres.py

Environment variables (same as the app):
    DB_PATH        — path to the existing platform.db   (default: ./data/platform.db)
    DATABASE_URL   — postgres DSN to migrate into       (required)
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection

# Reuse the canonical table definitions from the application.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from infrastructure.database.adapter import (  # noqa: E402
    metadata,
    audit_log_table,
    job_logs_table,
    node_group_nodes_table,
    profile_control_history_table,
    user_group_members_table,
)

# Tables whose primary key is a SERIAL (auto-increment integer) in PostgreSQL.
# After copying rows with explicit IDs we must advance the sequence past the
# highest value we inserted, otherwise the next auto-generated insert would
# collide with an existing row.
_SERIAL_TABLES = {
    job_logs_table.name,
    audit_log_table.name,
    profile_control_history_table.name,
    user_group_members_table.name,
    node_group_nodes_table.name,
}


async def _count(conn: AsyncConnection, table) -> int:
    result = await conn.execute(select(func.count()).select_from(table))
    return result.scalar() or 0


async def _migrate_table(sqlite_conn: AsyncConnection, pg_conn: AsyncConnection, table) -> int:
    existing = await _count(pg_conn, table)
    if existing > 0:
        print(f"  {table.name:<35} already has {existing:>6} rows — skipping")
        return 0

    rows = (await sqlite_conn.execute(select(table))).mappings().all()
    if not rows:
        print(f"  {table.name:<35} empty in SQLite — nothing to copy")
        return 0

    # Insert in batches of 500 to avoid massive single statements.
    batch_size = 500
    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = [dict(r) for r in rows[i : i + batch_size]]
        await pg_conn.execute(table.insert(), batch)
        inserted += len(batch)

    # Reset the PostgreSQL sequence for SERIAL-keyed tables so subsequent
    # application inserts don't collide with the migrated rows.
    if table.name in _SERIAL_TABLES:
        await pg_conn.execute(text(
            f"SELECT setval("
            f"  pg_get_serial_sequence('{table.name}', 'id'),"
            f"  COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1,"
            f"  false"
            f")"
        ))

    print(f"  {table.name:<35} copied {inserted:>6} rows")
    return inserted


async def main() -> None:
    db_path = os.environ.get("DB_PATH", "./data/platform.db")
    database_url = os.environ.get("DATABASE_URL", "")

    if not database_url:
        print("ERROR: DATABASE_URL is not set.")
        print("       Export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db and retry.")
        sys.exit(1)

    if not os.path.isfile(db_path):
        print(f"ERROR: SQLite file not found at {db_path!r}")
        print("       Set DB_PATH to the correct location of platform.db")
        sys.exit(1)

    sqlite_url = f"sqlite+aiosqlite:///{db_path}"
    print(f"\nSource:      {sqlite_url}")
    print(f"Destination: {database_url.split('@')[-1]}\n")  # hide password

    sqlite_engine = create_async_engine(sqlite_url, echo=False)
    pg_engine = create_async_engine(database_url, echo=False)

    # Ensure the PostgreSQL schema exists.
    async with pg_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    print("PostgreSQL schema ready.\n")

    total_copied = 0
    # Migrate in dependency order (parents before children).
    ordered_tables = [
        t for t in metadata.sorted_tables
    ]

    async with sqlite_engine.connect() as sqlite_conn:
        async with pg_engine.begin() as pg_conn:
            for table in ordered_tables:
                total_copied += await _migrate_table(sqlite_conn, pg_conn, table)

    await sqlite_engine.dispose()
    await pg_engine.dispose()

    print(f"\nMigration complete — {total_copied} rows copied to PostgreSQL.")
    print("You can now set DATABASE_URL in your .env and restart the platform.")


if __name__ == "__main__":
    asyncio.run(main())
