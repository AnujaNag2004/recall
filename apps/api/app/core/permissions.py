"""Workspace role checks for API routes."""

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session


def require_role(minimum: WorkspaceRole) -> Callable[..., Awaitable[WorkspaceMember]]:
    """A dependency for routes with a `workspace_id` path parameter.

    Non-members get 404, not 403, so the API doesn't confirm that a workspace exists.
    """

    async def dependency(
        workspace_id: UUID,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_user_session)],
    ) -> WorkspaceMember:
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        if membership.role.rank < minimum.rank:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=f"Requires the {minimum.value} role or above"
            )
        return membership

    return dependency
