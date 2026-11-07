from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.db.session import DatabaseNotConfiguredError, get_engine
from app.main import create_app
from app.routers.health import get_database_check

ALLOWED_ORIGIN = "https://recall.example"


# These tests need no database, so they shadow the real-database fixtures in conftest.
@pytest.fixture
def app() -> FastAPI:
    return create_app(Settings(cors_origins=f"{ALLOWED_ORIGIN}, http://localhost:3000"))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_health_is_ok_without_a_database(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_is_ok_when_database_responds(app: FastAPI, client: AsyncClient) -> None:
    async def healthy() -> None:
        return None

    app.dependency_overrides[get_database_check] = lambda: healthy
    response = await client.get("/health/ready")
    assert response.status_code == 200


async def test_ready_is_503_and_hides_the_cause(app: FastAPI, client: AsyncClient) -> None:
    async def failing() -> None:
        raise ConnectionError("could not reach db.internal.example")

    app.dependency_overrides[get_database_check] = lambda: failing
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


async def test_cors_allows_only_configured_origins(client: AsyncClient) -> None:
    allowed = await client.options(
        "/health", headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "GET"}
    )
    assert allowed.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    blocked = await client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in blocked.headers


def test_settings_split_cors_origins() -> None:
    settings = Settings(cors_origins=" https://a.example ,https://b.example,")
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]


def test_engine_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.db.session.get_settings", lambda: Settings(database_url=None))
    get_engine.cache_clear()
    with pytest.raises(DatabaseNotConfiguredError):
        get_engine()
    get_engine.cache_clear()
