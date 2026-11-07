"""Database access.

The schema itself lives in `supabase/migrations/` (plain SQL), which is the single
source of truth; SQLAlchemy only maps onto it and never creates tables.

Request handlers get `get_user_session`, which runs as the signed-in user with
row-level security enforced. So a missing check in API code still can't read another
workspace's data: this is the second layer of defense behind `require_role`.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.engine import DatabaseNotConfiguredError, get_engine

__all__ = ["DatabaseNotConfiguredError", "get_engine"]


async def check_database() -> None:
    """Run a trivial query; raises if the database cannot be reached."""
    async with get_engine().connect() as connection:
        await connection.execute(text("select 1"))


@asynccontextmanager
async def user_session(user: CurrentUser) -> AsyncIterator[AsyncSession]:
    """A transaction running as this user, exactly as a Supabase client request would.

    Both settings are transaction-local, so they can't leak to whoever uses this
    pooled connection next.
    """
    async with AsyncSession(get_engine(), expire_on_commit=False) as session, session.begin():
        claims = json.dumps({"sub": str(user.id), "role": "authenticated"})
        await session.execute(
            text("select set_config('request.jwt.claims', :claims, true)"), {"claims": claims}
        )
        await session.execute(text("set local role authenticated"))
        yield session


async def get_user_session(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AsyncIterator[AsyncSession]:
    async with user_session(user) as session:
        yield session


@asynccontextmanager
async def service_session() -> AsyncIterator[AsyncSession]:
    """For background workers only: runs outside row-level security, so no request
    handler may ever use this on a user's behalf."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session, session.begin():
        yield session
