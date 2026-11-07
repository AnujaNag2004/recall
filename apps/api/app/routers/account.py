"""Profile, API keys, usage, data export, account deletion and the agent run log."""

import contextlib
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.limits import usage_today
from app.core.permissions import require_role
from app.core.security import CurrentUser, generate_api_key, get_current_user, hash_api_key
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session, service_session
from app.services.storage import FileStore, StorageError, get_file_store

router = APIRouter(tags=["account"])

Admin = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.admin))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]
Config = Annotated[Settings, Depends(get_settings)]


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)


class UsageOut(BaseModel):
    used_today: int
    daily_cap: int


class ApiKeyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)


class ApiKeyOut(BaseModel):
    id: UUID
    label: str
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="Shown once. Only a hash is stored.")


class DeleteAccount(BaseModel):
    confirm: str = Field(description="Must be exactly: delete my account")


class AgentRunOut(BaseModel):
    id: UUID
    graph: str
    status: str
    save_id: UUID | None
    latency_ms: int | None
    tokens_in: int | None
    tokens_out: int | None
    error: str | None
    created_at: datetime


@router.patch("/me", status_code=status.HTTP_204_NO_CONTENT)
async def update_profile(body: ProfileUpdate, user: User, session: Session) -> None:
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        return
    if name := fields.get("name"):
        await session.execute(
            text("update public.profiles set name = :v where user_id = :u"),
            {"v": name, "u": user.id},
        )
    if timezone := fields.get("timezone"):
        await session.execute(
            text("update public.profiles set timezone = :v where user_id = :u"),
            {"v": timezone, "u": user.id},
        )


@router.get("/me/usage")
async def get_usage(user: User, settings: Config) -> UsageOut:
    return UsageOut(used_today=await usage_today(user.id), daily_cap=settings.daily_ai_usage_cap)


@router.get("/api-keys")
async def list_api_keys(user: User) -> list[ApiKeyOut]:
    async with service_session() as session:
        rows = await session.execute(
            text(
                "select id, label, last_used_at, created_at from public.api_keys "
                "where user_id = :u order by created_at desc"
            ),
            {"u": user.id},
        )
    return [ApiKeyOut(**dict(row._mapping)) for row in rows]


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(body: ApiKeyCreate, user: User) -> ApiKeyCreated:
    key = generate_api_key()
    async with service_session() as session:
        row = (
            await session.execute(
                text(
                    """
                    insert into public.api_keys (user_id, hashed_key, label)
                    values (:u, :hash, :label)
                    returning id, label, last_used_at, created_at
                    """
                ),
                {"u": user.id, "hash": hash_api_key(key), "label": body.label},
            )
        ).one()
    return ApiKeyCreated(**dict(row._mapping), key=key)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(key_id: UUID, user: User) -> None:
    async with service_session() as session:
        await session.execute(
            text("delete from public.api_keys where id = :id and user_id = :u"),
            {"id": key_id, "u": user.id},
        )


@router.get("/me/export")
async def export_data(user: User, session: Session) -> dict[str, Any]:
    """Everything this user can see in the workspaces they own, as JSON."""

    async def rows(sql: str) -> list[dict[str, Any]]:
        result = await session.execute(text(sql), {"u": user.id})
        return [dict(row._mapping) for row in result]

    owned = "select id from public.workspaces where owner_id = :u"
    return {
        "exported_at": datetime.now().astimezone().isoformat(),
        "profile": await rows(
            "select name, avatar_url, timezone, preferences from public.profiles where user_id = :u"
        ),
        "workspaces": await rows(
            "select id, name, type::text as type from public.workspaces where owner_id = :u"
        ),
        "saves": await rows(
            "select id, workspace_id, source_url, source_type, title, mode::text as mode, intent, "
            f"summary, key_points, raw_text, created_at from public.saves "
            f"where workspace_id in ({owned})"
        ),
        "tasks": await rows(
            "select id, workspace_id, save_id, title, description, status::text as status, "
            f"due_at, scheduled_for, completed_at from public.tasks "
            f"where workspace_id in ({owned})"
        ),
        "flashcards": await rows(
            f"select id, save_id, front, back from public.flashcards "
            f"where workspace_id in ({owned})"
        ),
        "conversations": await rows(
            "select c.id, c.title, m.role::text as role, m.content, m.created_at "
            "from public.conversations c join public.messages m on m.conversation_id = c.id "
            "where c.user_id = :u order by m.created_at"
        ),
    }


def _optional_files() -> FileStore | None:
    try:
        return get_file_store()
    except StorageError:
        return None


async def owned_file_paths(user_id: UUID) -> list[str]:
    """Uploads in the workspaces this person owns: exactly the saves deletion cascades to."""
    async with service_session() as session:
        rows = await session.scalars(
            text(
                "select s.storage_path from public.saves s "
                "join public.workspaces w on w.id = s.workspace_id "
                "where w.owner_id = :u and s.storage_path is not null"
            ),
            {"u": user_id},
        )
        return list(rows)


async def delete_auth_user(supabase_url: str, key: str, user_id: UUID) -> bool:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.delete(
            f"{supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {key}", "apikey": key},
        )
    return response.status_code < 400


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: DeleteAccount,
    user: User,
    settings: Config,
    files: Annotated[FileStore | None, Depends(_optional_files)],
) -> None:
    if body.confirm != "delete my account":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Confirmation didn't match")
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Account deletion is unavailable")
    # Read before deleting: the rows that point at these files go with the account.
    paths = await owned_file_paths(user.id)
    deleted = await delete_auth_user(
        settings.supabase_url, settings.supabase_service_role_key, user.id
    )
    if not deleted:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Your account couldn't be deleted")
    # Foreign keys cascade from auth.users, removing every row the person owns. Files in
    # Storage aren't rows, so they're removed here. One failure shouldn't stop the rest.
    if files:
        for path in paths:
            with contextlib.suppress(StorageError):
                await files.delete(path)


@router.get("/workspaces/{workspace_id}/agent-runs")
async def list_agent_runs(workspace_id: UUID, admin: Admin) -> list[AgentRunOut]:
    """Admins only: require_role has checked, and this table has no client access."""
    async with service_session() as session:
        rows = await session.execute(
            text(
                """
                select r.id, r.graph, r.status::text as status, r.save_id, r.latency_ms,
                       r.tokens_in, r.tokens_out, r.error, r.created_at
                from public.agent_runs r join public.saves s on s.id = r.save_id
                where s.workspace_id = :w
                order by r.created_at desc limit 100
                """
            ),
            {"w": workspace_id},
        )
    return [AgentRunOut(**dict(row._mapping)) for row in rows]
