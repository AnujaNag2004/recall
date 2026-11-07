"""The in-app calendar, .ics export and the optional Google Calendar connection."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.permissions import require_role
from app.core.security import CurrentUser, decrypt_secret, encrypt_secret, get_current_user
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session, service_session
from app.services.ics import IcsEvent, build_ics

router = APIRouter(tags=["calendar"])

Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]
Config = Annotated[Settings, Depends(get_settings)]

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - a URL, not a secret
GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar.events"
STATE_LIFETIME = timedelta(minutes=10)


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime | None = None
    is_deadline: bool = False


class EventOut(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime | None
    source: str
    is_deadline: bool


class ConnectOut(BaseModel):
    url: str


class GoogleStatus(BaseModel):
    configured: bool
    connected: bool


class SyncOut(BaseModel):
    synced: int


@router.get("/workspaces/{workspace_id}/calendar/events")
async def list_events(
    workspace_id: UUID,
    viewer: Viewer,
    session: Session,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> list[EventOut]:
    rows = await session.execute(
        text(
            """
            select id, title, starts_at, ends_at, source::text as source, is_deadline
            from public.calendar_events
            where workspace_id = :w and starts_at >= :start and starts_at <= :end
            order by starts_at limit 500
            """
        ),
        {
            "w": workspace_id,
            "start": start or datetime.now(UTC) - timedelta(days=31),
            "end": end or datetime.now(UTC) + timedelta(days=90),
        },
    )
    return [EventOut(**dict(row._mapping)) for row in rows]


@router.post("/workspaces/{workspace_id}/calendar/events", status_code=status.HTTP_201_CREATED)
async def create_event(
    workspace_id: UUID, body: EventCreate, viewer: Viewer, user: User, session: Session
) -> EventOut:
    row = (
        await session.execute(
            text(
                """
                insert into public.calendar_events
                  (workspace_id, user_id, title, starts_at, ends_at, is_deadline)
                values (:w, :u, :t, :s, :e, :d)
                returning id, title, starts_at, ends_at, source::text as source, is_deadline
                """
            ),
            {
                "w": workspace_id,
                "u": user.id,
                "t": body.title,
                "s": body.starts_at,
                "e": body.ends_at,
                "d": body.is_deadline,
            },
        )
    ).one()
    return EventOut(**dict(row._mapping))


@router.delete("/calendar/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: UUID, session: Session) -> None:
    deleted = await session.scalar(
        text("delete from public.calendar_events where id = :id returning id"), {"id": event_id}
    )
    if deleted is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")


@router.get("/workspaces/{workspace_id}/calendar/export.ics")
async def export_ics(workspace_id: UUID, viewer: Viewer, user: User, session: Session) -> Response:
    now = datetime.now(UTC)
    events = await session.execute(
        text(
            """
            select id, title, starts_at, ends_at from public.calendar_events
            where workspace_id = :w and user_id = :u and starts_at >= :since
            """
        ),
        {"w": workspace_id, "u": user.id, "since": now - timedelta(days=30)},
    )
    tasks = await session.execute(
        text(
            """
            select id, title, coalesce(scheduled_for, due_at) as starts_at from public.tasks
            where workspace_id = :w and status = 'accepted' and assignee_id = :u
              and coalesce(scheduled_for, due_at) is not null
            """
        ),
        {"w": workspace_id, "u": user.id},
    )
    items = [IcsEvent(f"event-{r.id}", r.title, r.starts_at, r.ends_at) for r in events]
    items += [IcsEvent(f"task-{r.id}", r.title, r.starts_at) for r in tasks]
    return Response(
        build_ics(items, now),
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="recall.ics"'},
    )


def _state_key(settings: Settings) -> str:
    if not settings.token_encryption_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google isn't configured")
    return settings.token_encryption_key


def _google_ready(settings: Settings) -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
        and settings.token_encryption_key
    )


@router.get("/integrations/google/status")
async def google_status(user: User, settings: Config) -> GoogleStatus:
    async with service_session() as session:
        found = await session.scalar(
            text(
                "select 1 from public.connected_accounts where user_id = :u and provider = 'google'"
            ),
            {"u": user.id},
        )
    return GoogleStatus(configured=_google_ready(settings), connected=bool(found))


@router.post("/integrations/google/connect")
async def google_connect(user: User, settings: Config) -> ConnectOut:
    if not _google_ready(settings):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google isn't configured")
    # A signed state ties the callback to this user, which stops login-CSRF style attacks.
    state = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + STATE_LIFETIME, "aud": "google-connect"},
        _state_key(settings),
        algorithm="HS256",
    )
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return ConnectOut(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/integrations/google/callback", include_in_schema=False)
async def google_callback(
    settings: Config, code: str | None = None, state: str | None = None
) -> RedirectResponse:
    """Google redirects the browser here, so the signed state stands in for a session."""
    base = settings.cors_origin_list[0] if settings.cors_origin_list else ""
    failed = RedirectResponse(f"{base}/settings?google=failed")
    if not code or not state:
        return failed
    try:
        claims = jwt.decode(
            state, _state_key(settings), algorithms=["HS256"], audience="google-connect"
        )
    except jwt.PyJWTError:
        return failed
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
    except httpx.HTTPError:
        return failed
    if response.status_code != 200:
        return failed
    tokens = response.json()
    async with service_session() as session:
        await session.execute(
            text(
                """
                insert into public.connected_accounts
                  (user_id, provider, encrypted_access_token, encrypted_refresh_token,
                   token_expires_at, scopes)
                values (:u, 'google', :access, :refresh, :expires, :scopes)
                on conflict (user_id, provider) do update set
                  encrypted_access_token = excluded.encrypted_access_token,
                  encrypted_refresh_token = coalesce(
                    excluded.encrypted_refresh_token,
                    public.connected_accounts.encrypted_refresh_token
                  ),
                  token_expires_at = excluded.token_expires_at,
                  scopes = excluded.scopes
                """
            ),
            {
                "u": UUID(claims["sub"]),
                "access": encrypt_secret(tokens["access_token"], settings),
                "refresh": (
                    encrypt_secret(tokens["refresh_token"], settings)
                    if tokens.get("refresh_token")
                    else None
                ),
                "expires": datetime.now(UTC) + timedelta(seconds=int(tokens.get("expires_in", 0))),
                "scopes": [GOOGLE_SCOPE],
            },
        )
    return RedirectResponse(f"{base}/settings?google=connected")


async def _google_token(user_id: UUID, settings: Settings) -> str:
    async with service_session() as session:
        row = (
            await session.execute(
                text(
                    """
                    select encrypted_access_token, encrypted_refresh_token, token_expires_at
                    from public.connected_accounts where user_id = :u and provider = 'google'
                    """
                ),
                {"u": user_id},
            )
        ).first()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Google Calendar first")
    if row.token_expires_at and row.token_expires_at > datetime.now(UTC) + timedelta(minutes=1):
        return decrypt_secret(row.encrypted_access_token, settings)
    if not row.encrypted_refresh_token:
        raise HTTPException(status.HTTP_409_CONFLICT, "Please reconnect Google Calendar")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": decrypt_secret(row.encrypted_refresh_token, settings),
                "grant_type": "refresh_token",
            },
        )
    if response.status_code != 200:
        raise HTTPException(status.HTTP_409_CONFLICT, "Please reconnect Google Calendar")
    tokens = response.json()
    async with service_session() as session:
        await session.execute(
            text(
                """
                update public.connected_accounts
                set encrypted_access_token = :access, token_expires_at = :expires
                where user_id = :u and provider = 'google'
                """
            ),
            {
                "access": encrypt_secret(tokens["access_token"], settings),
                "expires": datetime.now(UTC) + timedelta(seconds=int(tokens.get("expires_in", 0))),
                "u": user_id,
            },
        )
    return str(tokens["access_token"])


def _google_time(value: dict[str, str]) -> datetime | None:
    raw = value.get("dateTime") or value.get("date")
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@router.post("/workspaces/{workspace_id}/calendar/google/sync")
async def google_sync(workspace_id: UUID, viewer: Viewer, user: User, settings: Config) -> SyncOut:
    """Reads the next week of Google events, so just-in-time recall can use them."""
    token = await _google_token(user.id, settings)
    now = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            GOOGLE_EVENTS_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": now.isoformat(),
                "timeMax": (now + timedelta(days=7)).isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": "100",
            },
        )
    if response.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google Calendar didn't respond")
    count = 0
    async with service_session() as session:
        for item in response.json().get("items", []):
            start = _google_time(item.get("start", {}))
            if start is None or not item.get("id"):
                continue
            await session.execute(
                text(
                    """
                    insert into public.calendar_events
                      (workspace_id, user_id, title, starts_at, ends_at, source, external_id)
                    values (:w, :u, :t, :s, :e, 'google', :x)
                    on conflict (user_id, source, external_id) do update set
                      title = excluded.title, starts_at = excluded.starts_at,
                      ends_at = excluded.ends_at
                    """
                ),
                {
                    "w": workspace_id,
                    "u": user.id,
                    "t": str(item.get("summary") or "Busy")[:200],
                    "s": start,
                    "e": _google_time(item.get("end", {})),
                    "x": item["id"],
                },
            )
            count += 1
    return SyncOut(synced=count)


@router.post("/tasks/{task_id}/add-to-google", status_code=status.HTTP_201_CREATED)
async def add_task_to_google(
    task_id: UUID, user: User, session: Session, settings: Config
) -> SyncOut:
    """A side effect outside Recall, so this only ever runs from an explicit user click."""
    task = (
        await session.execute(
            text(
                "select title, coalesce(scheduled_for, due_at) as starts_at "
                "from public.tasks where id = :id"
            ),
            {"id": task_id},
        )
    ).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    if task.starts_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Give this task a time first")
    token = await _google_token(user.id, settings)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            GOOGLE_EVENTS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "summary": task.title,
                "start": {"dateTime": task.starts_at.isoformat()},
                "end": {"dateTime": (task.starts_at + timedelta(minutes=30)).isoformat()},
            },
        )
    if response.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google Calendar refused that")
    return SyncOut(synced=1)


@router.delete("/integrations/google", status_code=status.HTTP_204_NO_CONTENT)
async def google_disconnect(user: User) -> None:
    async with service_session() as session:
        await session.execute(
            text(
                "delete from public.connected_accounts where user_id = :u and provider = 'google'"
            ),
            {"u": user.id},
        )
