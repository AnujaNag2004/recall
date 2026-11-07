"""The database engine, kept apart so authentication can use it without an import cycle."""

from functools import lru_cache

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
