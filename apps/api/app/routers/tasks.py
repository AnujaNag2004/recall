"""Tasks and the follow-up loop: every change is logged, which powers the score."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.permissions import require_role
from app.core.security import CurrentUser, get_current_user
from app.db.models import ActionEvent, Save, Task, WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session
from app.schemas.tasks import TaskCreate, TaskOut, TaskResponse, TaskResponseOut, TaskUpdate

router = APIRouter(tags=["tasks"])

Member = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.member))]
Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]

DEFAULT_FOLLOWUP = timedelta(days=1)
# How long after a scheduled time to ask "Did you do it?".
FOLLOWUP_GRACE = timedelta(hours=1)


def task_out(task: Task, save_title: str | None = None) -> TaskOut:
    return TaskOut.model_validate(task, from_attributes=True).model_copy(
        update={"save_title": save_title}
    )


async def _get_task(session: AsyncSession, task_id: UUID) -> Task:
    task = await session.scalar(select(Task).where(Task.id == task_id))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


async def _flush(session: AsyncSession) -> None:
    try:
        await session.flush()
    except StaleDataError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't edit this") from error


def _log(session: AsyncSession, task: Task, event: str) -> None:
    session.add(ActionEvent(task_id=task.id, event=event))


def _schedule_followup(task: Task, now: datetime) -> None:
    scheduled = task.scheduled_for
    task.followup_at = scheduled + FOLLOWUP_GRACE if scheduled else now + DEFAULT_FOLLOWUP


@router.get("/workspaces/{workspace_id}/tasks")
async def list_tasks(
    workspace_id: UUID,
    viewer: Viewer,
    session: Session,
    task_status: Annotated[list[str] | None, Query(alias="status")] = None,
    save_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[TaskOut]:
    query = (
        select(Task, Save.title)
        .outerjoin(Save, Save.id == Task.save_id)
        .where(Task.workspace_id == workspace_id)
        .order_by(Task.scheduled_for.asc().nulls_last(), Task.created_at.desc())
        .limit(limit)
    )
    if task_status:
        query = query.where(Task.status.in_(task_status))
    if save_id:
        query = query.where(Task.save_id == save_id)
    rows = await session.execute(query)
    return [task_out(task, title) for task, title in rows.all()]


@router.post("/workspaces/{workspace_id}/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    workspace_id: UUID, body: TaskCreate, member: Member, user: User, session: Session
) -> TaskOut:
    now = datetime.now(UTC)
    task = Task(
        workspace_id=workspace_id,
        save_id=body.save_id,
        title=body.title,
        description=body.description,
        due_at=body.due_at,
        scheduled_for=body.scheduled_for,
        assignee_id=body.assignee_id or user.id,
        status="accepted",
    )
    _schedule_followup(task, now)
    session.add(task)
    await session.flush()
    _log(session, task, "accepted")
    await session.flush()
    await session.refresh(task)
    return task_out(task)


@router.patch("/tasks/{task_id}")
async def update_task(task_id: UUID, body: TaskUpdate, user: User, session: Session) -> TaskOut:
    task = await _get_task(session, task_id)
    now = datetime.now(UTC)
    fields: dict[str, Any] = body.model_dump(exclude_unset=True)
    new_status = fields.pop("status", None)
    rescheduled = "scheduled_for" in fields and fields["scheduled_for"] != task.scheduled_for
    for field, value in fields.items():
        setattr(task, field, value)
    if rescheduled:
        _schedule_followup(task, now)
        _log(session, task, "rescheduled")
    if new_status and new_status != task.status:
        task.status = new_status
        if new_status == "accepted":
            task.assignee_id = task.assignee_id or user.id
            _schedule_followup(task, now)
        else:
            task.followup_at = None
        _log(session, task, new_status)
    await _flush(session)
    return task_out(task)


@router.post("/tasks/{task_id}/respond")
async def respond_to_followup(
    task_id: UUID, body: TaskResponse, user: User, session: Session
) -> TaskResponseOut:
    """Did you do it? Done, not yet, or let go."""
    task = await _get_task(session, task_id)
    now = datetime.now(UTC)
    next_step: Task | None = None

    if body.answer == "done":
        task.status = "done"
        task.completed_at = now
        task.followup_at = None
        _log(session, task, "done")
        if task.save_id:
            next_step = await session.scalar(
                select(Task)
                .where(
                    Task.save_id == task.save_id,
                    Task.status == "suggested",
                    Task.id != task.id,
                )
                .order_by(Task.created_at)
                .limit(1)
            )
    elif body.answer == "not_yet":
        task.skip_count += 1
        task.status = "accepted"
        task.scheduled_for = body.reschedule_to or now + DEFAULT_FOLLOWUP
        _schedule_followup(task, now)
        _log(session, task, "skipped")
    else:
        task.status = "let_go"
        task.followup_at = None
        _log(session, task, "let_go")

    await _flush(session)
    return TaskResponseOut(
        task=task_out(task), next_step=task_out(next_step) if next_step else None
    )


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, session: Session) -> None:
    await _get_task(session, task_id)
    deleted = await session.scalar(delete(Task).where(Task.id == task_id).returning(Task.id))
    if deleted is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't delete this")
