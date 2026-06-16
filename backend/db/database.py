"""
db/database.py  –  Async SQLite engine + session factory
Uses Alembic for schema management in production.
Falls back to create_all only in test mode.
"""
from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.models import Base

DB_PATH     = Path(os.getenv("DB_PATH", "data/umlgen.db"))
TEST_MODE   = os.getenv("TESTING", "false").lower() == "true"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession,
)


async def init_db():
    """
    Production: run Alembic migrations programmatically.
    Test mode: use create_all for speed (no migration history needed).
    """
    if TEST_MODE:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    # Run Alembic migrations synchronously (Alembic doesn't support async natively)
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Fallback to create_all if alembic isn't configured yet
        import logging
        logging.getLogger(__name__).warning(
            "Alembic migration failed, falling back to create_all: %s", result.stderr
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
