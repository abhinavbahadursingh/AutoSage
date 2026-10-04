"""Probe database connectivity, tables, and row counts."""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.core.config import settings
from app.db import session as db

TABLES = [
    "users",
    "workspaces",
    "projects",
    "datasets",
    "experiments",
    "pipelines",
    "pipeline_runs",
    "agent_executions",
    "decisions",
    "evidence_trail_nodes",
    "verifications",
    "experience_memories",
    "ml_runs",
    "artifacts",
    "file_metadata",
    "reproducibility_records",
]


async def main() -> int:
    print(f"url={settings.DATABASE_URL.split('@')[-1][:70]}")
    db.init_engine()
    assert db.AsyncSessionLocal is not None
    async with db.AsyncSessionLocal() as session:
        try:
            r = await session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY 1"
                )
            )
            tables = [row[0] for row in r]
        except Exception as exc:
            print(f"CONNECT_FAIL: {type(exc).__name__}: {exc}")
            return 1
        print(f"tables={len(tables)}: {', '.join(tables)}")
        for t in TABLES:
            if t not in tables:
                print(f"  {t}: MISSING")
                continue
            try:
                cnt = await session.execute(text(f"SELECT count(*) FROM {t}"))
                print(f"  {t}: {cnt.scalar()}")
            except Exception as exc:
                await session.rollback()
                print(f"  {t}: ERR {type(exc).__name__}: {str(exc)[:80]}")
        if "alembic_version" in tables:
            cols = await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='alembic_version'"
                )
            )
            col_names = [row[0] for row in cols]
            col = "version" if "version" in col_names else "version_num"
            ver = await session.execute(text(f"SELECT {col} FROM alembic_version"))
            print(f"alembic={ver.scalar()} cols={col_names}")
        else:
            print("alembic=NO_TABLE")
        # pgvector extension?
        try:
            ext = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname='vector'")
            )
            print(f"pgvector={bool(ext.scalar())}")
        except Exception as exc:
            print(f"pgvector_err={exc}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
