"""Async database engine.

The schema itself lives in `supabase/migrations/` (plain SQL), which is the single
source of truth; SQLAlchemy only maps onto it and never creates tables.
"""

from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when DATABASE_URL is not set."""


@lru_cache
def get_engine() -> AsyncEngine:
    url = get_settings().database_url
    if not url:
        raise DatabaseNotConfiguredError("DATABASE_URL is not set")
    return create_async_engine(
        url,
        pool_pre_ping=True,
        # Supabase's connection pooler runs in transaction mode, which does not
        # support the prepared-statement cache asyncpg keeps by default.
        connect_args={"statement_cache_size": 0},
    )


async def check_database() -> None:
    """Run a trivial query; raises if the database cannot be reached."""
    async with get_engine().connect() as connection:
        await connection.execute(text("select 1"))
