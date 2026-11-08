"""Team workspaces, members, invites and meeting briefings."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scheduled import Briefing
from app.core.demo import forbid_demo
from app.core.limits import enforce_ai_limits
from app.core.permissions import require_role
from app.core.security import CurrentUser, get_current_user
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session, service_session
from app.guardrails.content import UNTRUSTED_SYSTEM_RULE, wrap_untrusted
from app.providers.base import ProviderError
from app.providers.registry import Providers, get_providers
from app.providers.structured import complete_structured
from app.services.retrieval import SearchFilters, hybrid_search

router = APIRouter(tags=["workspaces"])

Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Admin = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.admin))]
Owner = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.owner))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]

INVITE_LIFETIME = timedelta(days=7)
AssignableRole = Literal["admin", "member", "viewer"]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WorkspaceRename(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WorkspaceRef(BaseModel):
    id: UUID
    name: str
    type: str
    role: str


class MemberOut(BaseModel):
    user_id: UUID
    name: str | None
    avatar_url: str | None
    role: str


class RoleUpdate(BaseModel):
    role: AssignableRole


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: AssignableRole = "member"


class InviteOut(BaseModel):
    id: UUID
    email: str
    role: str
    token: str
    expires_at: datetime


class PrepBody(BaseModel):
    about: str = Field(min_length=1, max_length=300)


class PrepSave(BaseModel):
    id: UUID
    title: str | None


class PrepOut(BaseModel):
    summary: str
    saves: list[PrepSave]


@router.post(
    "/workspaces", status_code=status.HTTP_201_CREATED, dependencies=[Depends(forbid_demo)]
)
async def create_workspace(body: WorkspaceCreate, user: User, session: Session) -> WorkspaceRef:
    row = (
        await session.execute(
            text(
                "insert into public.workspaces (name, type, owner_id) "
                "values (:name, 'team', :owner) returning id, name, type::text as type"
            ),
            {"name": body.name, "owner": user.id},
        )
    ).one()
    return WorkspaceRef(**dict(row._mapping), role="owner")


@router.patch("/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_workspace(
    workspace_id: UUID, body: WorkspaceRename, admin: Admin, session: Session
) -> None:
    await session.execute(
        text("update public.workspaces set name = :name where id = :id"),
        {"name": body.name, "id": workspace_id},
    )


@router.delete("/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: UUID, owner: Owner, session: Session) -> None:
    kind = await session.scalar(
        text("select type::text from public.workspaces where id = :id"), {"id": workspace_id}
    )
    if kind == "personal":
        raise HTTPException(status.HTTP_409_CONFLICT, "Your personal workspace can't be deleted")
    await session.execute(
        text("delete from public.workspaces where id = :id"), {"id": workspace_id}
    )


@router.get("/workspaces/{workspace_id}/members")
async def list_members(workspace_id: UUID, viewer: Viewer, session: Session) -> list[MemberOut]:
    rows = await session.execute(
        text(
            """
            select m.user_id, p.name, p.avatar_url, m.role::text as role
            from public.workspace_members m
            left join public.profiles p on p.user_id = m.user_id
            where m.workspace_id = :w
            order by m.created_at
            """
        ),
        {"w": workspace_id},
    )
    return [MemberOut(**dict(row._mapping)) for row in rows]


@router.patch(
    "/workspaces/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def change_role(
    workspace_id: UUID, user_id: UUID, body: RoleUpdate, admin: Admin, session: Session
) -> None:
    # Row-level security refuses to touch an owner's row, so nothing is returned for one.
    changed = await session.scalar(
        text(
            """
            update public.workspace_members set role = cast(:role as public.workspace_role)
            where workspace_id = :w and user_id = :u returning id
            """
        ),
        {"role": body.role, "w": workspace_id, "u": user_id},
    )
    if changed is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That member's role can't be changed")


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    workspace_id: UUID, user_id: UUID, viewer: Viewer, session: Session
) -> None:
    """Admins can remove members, and anyone but the owner can leave."""
    removed = await session.scalar(
        text(
            "delete from public.workspace_members where workspace_id = :w and user_id = :u "
            "returning id"
        ),
        {"w": workspace_id, "u": user_id},
    )
    if removed is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That member can't be removed")


@router.post(
    "/workspaces/{workspace_id}/invites",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(forbid_demo)],
)
async def create_invite(
    workspace_id: UUID, body: InviteCreate, admin: Admin, session: Session
) -> InviteOut:
    """Returns a link for the person inviting to share. Nothing is sent automatically."""
    row = (
        await session.execute(
            text(
                """
                insert into public.invites (workspace_id, email, token, role, expires_at)
                values (:w, :email, :token, cast(:role as public.workspace_role), :expires)
                returning id, email, role::text as role, token, expires_at
                """
            ),
            {
                "w": workspace_id,
                "email": body.email.strip().lower(),
                "token": secrets.token_urlsafe(32),
                "role": body.role,
                "expires": datetime.now(UTC) + INVITE_LIFETIME,
            },
        )
    ).one()
    return InviteOut(**dict(row._mapping))


@router.get("/workspaces/{workspace_id}/invites")
async def list_invites(workspace_id: UUID, admin: Admin, session: Session) -> list[InviteOut]:
    rows = await session.execute(
        text(
            """
            select id, email, role::text as role, token, expires_at from public.invites
            where workspace_id = :w and expires_at > now() order by created_at desc
            """
        ),
        {"w": workspace_id},
    )
    return [InviteOut(**dict(row._mapping)) for row in rows]


@router.delete(
    "/workspaces/{workspace_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_invite(
    workspace_id: UUID, invite_id: UUID, admin: Admin, session: Session
) -> None:
    await session.execute(
        text("delete from public.invites where id = :id and workspace_id = :w"),
        {"id": invite_id, "w": workspace_id},
    )


@router.post("/invites/{token}/accept", dependencies=[Depends(forbid_demo)])
async def accept_invite(token: str, user: User) -> WorkspaceRef:
    """The accepter isn't a member yet, so RLS would hide the invite: this needs service
    access. The token and the email together are what authorize it."""
    async with service_session() as session:
        invite = (
            await session.execute(
                text(
                    """
                    select i.id, i.workspace_id, i.email, i.role::text as role, i.expires_at,
                           w.name, w.type::text as type
                    from public.invites i join public.workspaces w on w.id = i.workspace_id
                    where i.token = :token
                    """
                ),
                {"token": token},
            )
        ).first()
        if invite is None or invite.expires_at <= datetime.now(UTC):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "This invite has expired or was already used"
            )
        if not user.email or user.email.strip().lower() != invite.email:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This invite was sent to a different email address than the one you signed in "
                f"with. Sign in as {invite.email} to accept it.",
            )
        await session.execute(
            text(
                """
                insert into public.workspace_members (workspace_id, user_id, role)
                values (:w, :u, cast(:role as public.workspace_role))
                on conflict (workspace_id, user_id) do nothing
                """
            ),
            {"w": invite.workspace_id, "u": user.id, "role": invite.role},
        )
        await session.execute(text("delete from public.invites where id = :id"), {"id": invite.id})
    return WorkspaceRef(
        id=invite.workspace_id, name=invite.name, type=invite.type, role=invite.role
    )


@router.post("/workspaces/{workspace_id}/prep", dependencies=[Depends(enforce_ai_limits)])
async def prep_me(
    workspace_id: UUID,
    body: PrepBody,
    viewer: Viewer,
    session: Session,
    providers: Annotated[Providers, Depends(get_providers)],
) -> PrepOut:
    """'Prep me for this meeting': gathers related saves into a briefing card."""
    try:
        embedding = (await providers.embeddings.embed([body.about]))[0]
        chunks = await hybrid_search(
            session, body.about, embedding, SearchFilters(workspace_id), limit=8
        )
        if not chunks:
            return PrepOut(summary="Nothing saved here relates to that yet.", saves=[])
        excerpts = "\n\n".join(wrap_untrusted(chunk.text[:700]) for chunk in chunks)
        briefing = await complete_structured(
            providers.llm,
            f"Prepare the person for this: {body.about!r}. In two to four sentences, cover what "
            f"they most need to remember from these saved notes.\n\n{excerpts}",
            Briefing,
            system=UNTRUSTED_SYSTEM_RULE,
        )
    except ProviderError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The AI service is unavailable right now."
        ) from error
    saves = {chunk.save_id: chunk.save_title for chunk in chunks}
    return PrepOut(
        summary=briefing.summary,
        saves=[PrepSave(id=save_id, title=title) for save_id, title in saves.items()],
    )
