"""The signed-in user and the workspaces they belong to."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import CurrentUser, get_current_user
from app.db.models import Profile, Workspace, WorkspaceMember, WorkspaceType
from app.db.session import get_user_session
from app.schemas.me import MeOut, UserOut, WorkspaceOut

router = APIRouter(tags=["me"])


@router.get("/me")
async def get_me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_user_session)],
) -> MeOut:
    profile = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    memberships = await session.scalars(
        select(WorkspaceMember)
        .options(joinedload(WorkspaceMember.workspace))
        .join(Workspace)
        .where(WorkspaceMember.user_id == user.id)
        # The personal workspace first, then team workspaces, oldest first.
        .order_by(Workspace.type != WorkspaceType.personal, Workspace.created_at)
    )
    return MeOut(
        user=UserOut(
            id=user.id,
            email=user.email,
            name=profile.name if profile else None,
            avatar_url=profile.avatar_url if profile else None,
            timezone=profile.timezone if profile else "UTC",
        ),
        workspaces=[
            WorkspaceOut(
                id=member.workspace.id,
                name=member.workspace.name,
                type=member.workspace.type,
                role=member.role,
            )
            for member in memberships
        ],
    )
