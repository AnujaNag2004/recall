"""Today's view, the score and just-in-time recall."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.core.security import CurrentUser, get_current_user
from app.db.models import Save, Task, WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session
from app.routers.tasks import task_out
from app.schemas.saves import SaveSummaryOut
from app.schemas.tasks import TaskOut
from app.services.metrics import compute_metrics

router = APIRouter(tags=["home"])

Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]


class RecallCardOut(BaseModel):
    id: UUID
    title: str
    body: str
    save_ids: list[UUID]
    expires_at: datetime


class ScoreOut(BaseModel):
    acted: int
    total: int
    ratio: float


class HomeOut(BaseModel):
    recall_cards: list[RecallCardOut]
    followups: list[TaskOut] = Field(description="Tasks waiting on 'Did you do it?'")
    today: list[TaskOut]
    suggested: list[TaskOut]
    review_count: int
    score: ScoreOut
    streak_days: int
    recent_saves: list[SaveSummaryOut]


class MetricsOut(BaseModel):
    score: ScoreOut
    streak_days: int
    categories: list[dict[str, Any]]
    trend: list[dict[str, Any]]
    changed: list[dict[str, Any]]


@router.get("/workspaces/{workspace_id}/metrics/save-to-action")
async def save_to_action(workspace_id: UUID, viewer: Viewer, session: Session) -> MetricsOut:
    return MetricsOut(**await compute_metrics(session, workspace_id))


@router.get("/workspaces/{workspace_id}/home")
async def home(workspace_id: UUID, viewer: Viewer, user: User, session: Session) -> HomeOut:
    now = datetime.now(UTC)
    end_of_today = now.replace(hour=23, minute=59, second=59)

    async def tasks(*conditions: Any, limit: int = 20) -> list[TaskOut]:
        rows = await session.execute(
            select(Task, Save.title)
            .outerjoin(Save, Save.id == Task.save_id)
            .where(Task.workspace_id == workspace_id, *conditions)
            .order_by(Task.scheduled_for.asc().nulls_last(), Task.created_at.desc())
            .limit(limit)
        )
        return [task_out(task, title) for task, title in rows.all()]

    # A team's tasks may belong to others, so people only get nudged about their own.
    mine = Task.assignee_id == user.id
    followups = await tasks(Task.status == "accepted", mine, Task.followup_at <= now)
    followup_ids = {task.id for task in followups}
    today = [
        task
        for task in await tasks(Task.status == "accepted", mine, Task.scheduled_for <= end_of_today)
        if task.id not in followup_ids
    ]
    suggested = await tasks(Task.status == "suggested", Task.type == "micro_action", limit=5)
    cards = await session.execute(
        text(
            "select id, title, body, save_ids, expires_at from public.recall_cards "
            "where workspace_id = :w and dismissed_at is null and expires_at > now() "
            "order by expires_at limit 5"
        ),
        {"w": workspace_id},
    )
    review_count = await session.scalar(
        text("select count(*) from public.flashcards where workspace_id = :w and due_at <= now()"),
        {"w": workspace_id},
    )
    recent = await session.scalars(
        select(Save)
        .where(Save.workspace_id == workspace_id)
        .order_by(Save.created_at.desc())
        .limit(6)
    )
    metrics = await compute_metrics(session, workspace_id)
    return HomeOut(
        recall_cards=[RecallCardOut(**dict(row._mapping)) for row in cards],
        followups=followups,
        today=today,
        suggested=suggested,
        review_count=int(review_count or 0),
        score=ScoreOut(**metrics["score"]),
        streak_days=metrics["streak_days"],
        recent_saves=[SaveSummaryOut.model_validate(s, from_attributes=True) for s in recent],
    )


@router.post("/recall-cards/{card_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_card(card_id: UUID, session: Session) -> None:
    updated = await session.scalar(
        text("update public.recall_cards set dismissed_at = now() where id = :id returning id"),
        {"id": card_id},
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card not found")
