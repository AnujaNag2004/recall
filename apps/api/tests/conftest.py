"""Shared fixtures. API tests run against a real, embedded Postgres with pgvector."""

import shutil
import tempfile
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import jwt
import pgserver
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.security import TokenVerifier, get_token_verifier
from app.db.session import get_engine
from app.main import create_app

SUPABASE_DIR = Path(__file__).resolve().parents[3] / "supabase"
TEST_SUPABASE_URL = "https://test-project.supabase.co"
TEST_JWT_SECRET = "test-only-secret-that-is-long-enough-for-hs256"


@pytest.fixture(scope="session")
def postgres() -> Iterator[Any]:
    """One server per test run, with every migration applied."""
    # Fixed short parent: Unix socket paths are limited to about 100 characters.
    data_dir = tempfile.mkdtemp(prefix="recall-pg-", dir="/tmp")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")  # type: ignore[attr-defined]
    try:
        server.psql((SUPABASE_DIR / "local" / "auth_stub.sql").read_text())
        for migration in sorted((SUPABASE_DIR / "migrations").glob("*.sql")):
            server.psql(migration.read_text())
        yield server
    finally:
        server.cleanup()
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def settings(postgres: Any) -> Settings:
    socket_dir = postgres.get_uri().split("host=")[1]
    return Settings(
        database_url=f"postgresql+asyncpg://postgres@/postgres?host={socket_dir}",
        supabase_url=TEST_SUPABASE_URL,
        supabase_jwt_secret=TEST_JWT_SECRET,
    )


@pytest.fixture
async def app(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FastAPI]:
    monkeypatch.setattr("app.db.session.get_settings", lambda: settings)
    get_engine.cache_clear()
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(settings)
    yield application
    # Connections belong to this test's event loop, so they can't be reused.
    await get_engine().dispose()
    get_engine.cache_clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def make_token(user_id: UUID, **overrides: Any) -> str:
    claims = {
        "sub": str(user_id),
        "aud": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "role": "authenticated",
        "email": "person@example.com",
        "exp": int(time.time()) + 600,
        **overrides,
    }
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def auth_header(user_id: UUID, **overrides: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id, **overrides)}"}


def create_user(postgres: Any, name: str = "Test Person") -> UUID:
    """Inserts into auth.users, which fires the same signup trigger as production."""
    user_id = uuid4()
    postgres.psql(
        f"insert into auth.users (id, email, raw_user_meta_data) "
        f"values ('{user_id}', '{user_id}@example.com', '{{\"full_name\": \"{name}\"}}');"
    )
    return user_id


def create_team(postgres: Any, owner: UUID, members: dict[UUID, str] | None = None) -> UUID:
    workspace_id = uuid4()
    postgres.psql(
        f"insert into public.workspaces (id, name, type, owner_id) "
        f"values ('{workspace_id}', 'Team', 'team', '{owner}');"
    )
    for user_id, role in (members or {}).items():
        postgres.psql(
            f"insert into public.workspace_members (workspace_id, user_id, role) "
            f"values ('{workspace_id}', '{user_id}', '{role}');"
        )
    return workspace_id
