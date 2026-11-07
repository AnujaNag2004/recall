"""The API against a real database: signup trigger, RLS and role checks together."""

from typing import Annotated, Any
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_engine, get_user_session
from tests.conftest import auth_header, create_team, create_user


async def test_me_requires_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_rejects_an_expired_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me", headers=auth_header(uuid4(), exp=1))
    assert response.status_code == 401


async def test_new_user_lands_with_a_personal_workspace(client: AsyncClient, postgres: Any) -> None:
    user = create_user(postgres, name="Priya S")
    response = await client.get("/api/v1/me", headers=auth_header(user))
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["name"] == "Priya S"
    assert body["user"]["email"] == "person@example.com"
    assert [(w["name"], w["type"], w["role"]) for w in body["workspaces"]] == [
        ("Personal", "personal", "owner")
    ]


async def test_me_lists_the_personal_workspace_before_teams(
    client: AsyncClient, postgres: Any
) -> None:
    owner, user = create_user(postgres), create_user(postgres)
    create_team(postgres, owner, {user: "viewer"})
    response = await client.get("/api/v1/me", headers=auth_header(user))
    assert [(w["type"], w["role"]) for w in response.json()["workspaces"]] == [
        ("personal", "owner"),
        ("team", "viewer"),
    ]


async def test_me_never_shows_another_users_workspace(client: AsyncClient, postgres: Any) -> None:
    alice, bob = create_user(postgres), create_user(postgres)
    create_team(postgres, alice)
    response = await client.get("/api/v1/me", headers=auth_header(bob))
    assert len(response.json()["workspaces"]) == 1


async def test_a_token_for_an_unknown_user_sees_nothing(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me", headers=auth_header(uuid4()))
    assert response.status_code == 200
    assert response.json()["workspaces"] == []
    assert response.json()["user"]["name"] is None


async def test_handler_sessions_run_as_the_user_under_rls(
    app: FastAPI, client: AsyncClient, postgres: Any
) -> None:
    """The second layer: even a handler with no checks at all can't cross tenants."""
    alice, bob = create_user(postgres), create_user(postgres)
    team = create_team(postgres, alice)

    @app.get("/test/unchecked")
    async def unchecked(
        session: Annotated[AsyncSession, Depends(get_user_session)],
    ) -> dict[str, Any]:
        role = await session.scalar(text("select current_user"))
        ids = await session.scalars(text("select id from public.workspaces"))
        return {"role": role, "workspaces": [str(i) for i in ids]}

    body = (await client.get("/test/unchecked", headers=auth_header(bob))).json()
    assert body["role"] == "authenticated"
    assert str(team) not in body["workspaces"]
    assert len(body["workspaces"]) == 1


async def test_session_role_does_not_leak_to_the_next_request(
    app: FastAPI, client: AsyncClient, postgres: Any
) -> None:
    alice, bob = create_user(postgres), create_user(postgres)

    @app.get("/test/whoami")
    async def whoami(
        session: Annotated[AsyncSession, Depends(get_user_session)],
    ) -> dict[str, Any]:
        return {"uid": str(await session.scalar(text("select auth.uid()")))}

    for user in [alice, bob, alice]:
        body = (await client.get("/test/whoami", headers=auth_header(user))).json()
        assert body["uid"] == str(user)

    async with get_engine().connect() as connection:
        assert await connection.scalar(text("select current_user")) == "postgres"


@pytest.fixture
def admin_route(app: FastAPI) -> str:
    @app.get("/test/workspaces/{workspace_id}/admin-only")
    async def admin_only(
        membership: Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.admin))],
    ) -> dict[str, str]:
        return {"role": membership.role.value}

    return "/test/workspaces/{}/admin-only"


@pytest.mark.parametrize(
    ("role", "expected"),
    [("viewer", 403), ("member", 403), ("admin", 200)],
)
async def test_require_role_enforces_the_minimum(
    client: AsyncClient, postgres: Any, admin_route: str, role: str, expected: int
) -> None:
    owner, user = create_user(postgres), create_user(postgres)
    team = create_team(postgres, owner, {user: role})
    response = await client.get(admin_route.format(team), headers=auth_header(user))
    assert response.status_code == expected


async def test_require_role_lets_the_owner_through(
    client: AsyncClient, postgres: Any, admin_route: str
) -> None:
    owner = create_user(postgres)
    team = create_team(postgres, owner)
    response = await client.get(admin_route.format(team), headers=auth_header(owner))
    assert response.json() == {"role": "owner"}


async def test_require_role_hides_workspaces_from_non_members(
    client: AsyncClient, postgres: Any, admin_route: str
) -> None:
    owner, outsider = create_user(postgres), create_user(postgres)
    team: UUID = create_team(postgres, owner)
    response = await client.get(admin_route.format(team), headers=auth_header(outsider))
    assert response.status_code == 404
