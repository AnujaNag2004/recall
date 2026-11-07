"""Teams, invites, calendar export, API keys and account features."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import Settings, get_settings
from app.core.security import (
    AuthUnavailableError,
    decrypt_secret,
    encrypt_secret,
    generate_api_key,
    hash_api_key,
)
from app.providers.registry import get_providers
from app.services.ics import IcsEvent, build_ics
from tests.conftest import auth_header, create_team, create_user
from tests.fakes import FakeLLM, fake_providers
from tests.test_ingestion import create_note, drain_jobs


async def personal_workspace(client: AsyncClient, headers: dict[str, str]) -> str:
    return str((await client.get("/api/v1/me", headers=headers)).json()["workspaces"][0]["id"])


async def test_creating_a_team_makes_you_its_owner(client: AsyncClient, postgres: Any) -> None:
    headers = auth_header(create_user(postgres))
    response = await client.post("/api/v1/workspaces", headers=headers, json={"name": "Squad"})
    assert response.status_code == 201
    assert response.json()["role"] == "owner"
    me = (await client.get("/api/v1/me", headers=headers)).json()
    assert [w["name"] for w in me["workspaces"]] == ["Personal", "Squad"]


async def test_an_invite_works_for_the_right_email_only_and_only_once(
    client: AsyncClient, postgres: Any
) -> None:
    owner = create_user(postgres)
    team = create_team(postgres, owner)
    invited = create_user(postgres)
    created = await client.post(
        f"/api/v1/workspaces/{team}/invites",
        headers=auth_header(owner),
        json={"email": "Teammate@Example.com", "role": "viewer"},
    )
    assert created.status_code == 201
    token = created.json()["token"]

    wrong = auth_header(invited, email="someone.else@example.com")
    assert (await client.post(f"/api/v1/invites/{token}/accept", headers=wrong)).status_code == 403

    right = auth_header(invited, email="teammate@example.com")
    accepted = await client.post(f"/api/v1/invites/{token}/accept", headers=right)
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "viewer"
    me = (await client.get("/api/v1/me", headers=right)).json()
    assert str(team) in [w["id"] for w in me["workspaces"]]

    again = await client.post(f"/api/v1/invites/{token}/accept", headers=right)
    assert again.status_code == 404


async def test_expired_invites_are_refused(client: AsyncClient, postgres: Any) -> None:
    owner = create_user(postgres)
    team = create_team(postgres, owner)
    created = await client.post(
        f"/api/v1/workspaces/{team}/invites",
        headers=auth_header(owner),
        json={"email": "t@example.com"},
    )
    token = created.json()["token"]
    postgres.psql(
        f"update public.invites set expires_at = now() - interval '1 day' where token='{token}';"
    )
    response = await client.post(
        f"/api/v1/invites/{token}/accept",
        headers=auth_header(create_user(postgres), email="t@example.com"),
    )
    assert response.status_code == 404


async def test_members_cannot_invite_or_see_invites(client: AsyncClient, postgres: Any) -> None:
    owner, member = create_user(postgres), create_user(postgres)
    team = create_team(postgres, owner, {member: "member"})
    headers = auth_header(member)
    invite = await client.post(
        f"/api/v1/workspaces/{team}/invites", headers=headers, json={"email": "x@example.com"}
    )
    assert invite.status_code == 403
    assert (
        await client.get(f"/api/v1/workspaces/{team}/invites", headers=headers)
    ).status_code == 403


async def test_nobody_can_invite_an_owner(client: AsyncClient, postgres: Any) -> None:
    owner = create_user(postgres)
    team = create_team(postgres, owner)
    response = await client.post(
        f"/api/v1/workspaces/{team}/invites",
        headers=auth_header(owner),
        json={"email": "x@example.com", "role": "owner"},
    )
    assert response.status_code == 422


async def test_role_changes_respect_the_rules(client: AsyncClient, postgres: Any) -> None:
    owner, admin, member = create_user(postgres), create_user(postgres), create_user(postgres)
    team = create_team(postgres, owner, {admin: "admin", member: "member"})
    headers = auth_header(admin)
    url = f"/api/v1/workspaces/{team}/members"
    ok = await client.patch(f"{url}/{member}", headers=headers, json={"role": "viewer"})
    assert ok.status_code == 204
    denied = await client.patch(f"{url}/{owner}", headers=headers, json={"role": "viewer"})
    assert denied.status_code == 403
    assert (await client.delete(f"{url}/{owner}", headers=headers)).status_code == 403
    assert (await client.delete(f"{url}/{member}", headers=auth_header(member))).status_code == 204


async def test_personal_workspaces_cannot_be_deleted(client: AsyncClient, postgres: Any) -> None:
    headers = auth_header(create_user(postgres))
    workspace = await personal_workspace(client, headers)
    response = await client.delete(f"/api/v1/workspaces/{workspace}", headers=headers)
    assert response.status_code == 409


async def test_prep_briefs_from_workspace_saves(
    app: FastAPI, client: AsyncClient, settings: Settings, postgres: Any
) -> None:
    llm = FakeLLM({"Prepare the person": {"summary": "Remember the cycles point."}})
    app.dependency_overrides[get_providers] = lambda: fake_providers(llm=llm)
    headers = auth_header(create_user(postgres))
    workspace = await personal_workspace(client, headers)
    save_id = await create_note(client, (workspace, headers))
    await drain_jobs(settings)
    response = await client.post(
        f"/api/v1/workspaces/{workspace}/prep", headers=headers, json={"about": "cycles"}
    )
    assert response.json()["summary"] == "Remember the cycles point."
    assert [s["id"] for s in response.json()["saves"]] == [save_id]


def test_ics_escapes_and_folds() -> None:
    start = datetime(2026, 11, 7, 9, tzinfo=UTC)
    title = "Review, then; plan\nnext " + "long " * 30
    body = build_ics([IcsEvent("abc", title, start)], start)
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert "Review\\, then\\; plan\\nnext" in body
    assert "DTSTART:20261107T090000Z" in body
    assert "DTEND:20261107T093000Z" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))


async def test_calendar_export_downloads(client: AsyncClient, postgres: Any) -> None:
    headers = auth_header(create_user(postgres))
    workspace = await personal_workspace(client, headers)
    start = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    await client.post(
        f"/api/v1/workspaces/{workspace}/calendar/events",
        headers=headers,
        json={"title": "Exam", "starts_at": start, "is_deadline": True},
    )
    await client.post(
        f"/api/v1/workspaces/{workspace}/tasks",
        headers=headers,
        json={"title": "Revise", "scheduled_for": start},
    )
    response = await client.get(
        f"/api/v1/workspaces/{workspace}/calendar/export.ics", headers=headers
    )
    assert response.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Exam" in response.text
    assert "SUMMARY:Revise" in response.text


async def test_api_keys_authenticate_and_only_a_hash_is_stored(
    client: AsyncClient, postgres: Any
) -> None:
    user = create_user(postgres, name="Key User")
    headers = auth_header(user)
    created = await client.post("/api/v1/api-keys", headers=headers, json={"label": "Laptop"})
    key = created.json()["key"]
    assert key.startswith("rk_")
    assert key not in postgres.psql("select hashed_key from public.api_keys;")

    via_key = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {key}"})
    assert via_key.json()["user"]["name"] == "Key User"

    listed = (await client.get("/api/v1/api-keys", headers=headers)).json()
    assert "key" not in listed[0]
    assert listed[0]["last_used_at"]

    await client.delete(f"/api/v1/api-keys/{listed[0]['id']}", headers=headers)
    revoked = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {key}"})
    assert revoked.status_code == 401


async def test_api_keys_run_under_row_level_security(client: AsyncClient, postgres: Any) -> None:
    owner, stranger = create_user(postgres), create_user(postgres)
    team = create_team(postgres, owner)
    created = await client.post(
        "/api/v1/api-keys", headers=auth_header(stranger), json={"label": "k"}
    )
    headers = {"Authorization": f"Bearer {created.json()['key']}"}
    assert (
        await client.get(f"/api/v1/workspaces/{team}/saves", headers=headers)
    ).status_code == 404


async def test_an_unknown_api_key_is_refused(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {generate_api_key()}"}
    )
    assert response.status_code == 401


def test_key_hash_is_stable_and_different_from_the_key() -> None:
    key = generate_api_key()
    assert hash_api_key(key) == hash_api_key(key)
    assert hash_api_key(key) != key


def test_tokens_round_trip_encrypted() -> None:
    settings = Settings(token_encryption_key=Fernet.generate_key().decode())
    sealed = encrypt_secret("google-token", settings)
    assert "google-token" not in sealed
    assert decrypt_secret(sealed, settings) == "google-token"


def test_encryption_refuses_to_run_without_a_key() -> None:
    with pytest.raises(AuthUnavailableError):
        encrypt_secret("x", Settings(token_encryption_key=None))


async def test_google_callback_rejects_a_forged_state(
    app: FastAPI, client: AsyncClient, postgres: Any
) -> None:
    configured = Settings(
        token_encryption_key=Fernet.generate_key().decode(),
        google_client_id="id",
        google_client_secret="secret",
        google_redirect_uri="http://localhost/cb",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    response = await client.get(
        "/api/v1/integrations/google/callback", params={"code": "c", "state": "forged"}
    )
    assert response.status_code == 307
    assert "google=failed" in response.headers["location"]


async def test_google_status_reports_when_unconfigured(client: AsyncClient, postgres: Any) -> None:
    status_ = await client.get(
        "/api/v1/integrations/google/status", headers=auth_header(create_user(postgres))
    )
    assert status_.json() == {"configured": False, "connected": False}


async def test_export_contains_your_data_and_not_others(client: AsyncClient, postgres: Any) -> None:
    mine, theirs = auth_header(create_user(postgres)), auth_header(create_user(postgres))
    await create_note(client, (await personal_workspace(client, mine), mine))
    await create_note(client, (await personal_workspace(client, theirs), theirs))
    export = (await client.get("/api/v1/me/export", headers=mine)).json()
    assert len(export["saves"]) == 1
    assert export["profile"][0]["name"] == "Test Person"


async def test_delete_account_needs_exact_confirmation(client: AsyncClient, postgres: Any) -> None:
    response = await client.request(
        "DELETE",
        "/api/v1/me",
        headers=auth_header(create_user(postgres)),
        json={"confirm": "yes"},
    )
    assert response.status_code == 422


async def test_profile_updates(client: AsyncClient, postgres: Any) -> None:
    headers = auth_header(create_user(postgres))
    await client.patch(
        "/api/v1/me", headers=headers, json={"name": "New Name", "timezone": "Asia/Kolkata"}
    )
    me = (await client.get("/api/v1/me", headers=headers)).json()["user"]
    assert (me["name"], me["timezone"]) == ("New Name", "Asia/Kolkata")


async def test_agent_runs_are_recorded_for_admins_only(
    client: AsyncClient, settings: Settings, postgres: Any
) -> None:
    owner, member = create_user(postgres), create_user(postgres)
    team = create_team(postgres, owner, {member: "member"})
    await create_note(client, (str(team), auth_header(owner)))
    await drain_jobs(settings)
    runs = await client.get(f"/api/v1/workspaces/{team}/agent-runs", headers=auth_header(owner))
    assert runs.status_code == 200
    assert runs.json()[0]["graph"] == "ingestion"
    assert runs.json()[0]["status"] == "succeeded"
    denied = await client.get(f"/api/v1/workspaces/{team}/agent-runs", headers=auth_header(member))
    assert denied.status_code == 403
