from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ResourceOut(BaseModel):
    id: UUID
    name: str
    entity_type: str
    mention_ts: float | None
    url: str | None
    domain: str | None
    title: str | None
    description: str | None
    favicon_url: str | None
    pricing: str | None
    category: str | None
    confidence: float | None
    verified: bool


TaskStatus = Literal["suggested", "accepted", "done", "skipped", "let_go"]
TaskType = Literal["micro_action", "action_item", "checklist_item"]
TaskSize = Literal["tiny", "small", "medium"]


class TaskOut(BaseModel):
    id: UUID
    workspace_id: UUID
    save_id: UUID | None
    save_title: str | None = None
    title: str
    description: str | None
    type: TaskType
    assignee_id: UUID | None
    due_at: datetime | None
    scheduled_for: datetime | None
    status: TaskStatus
    size: TaskSize
    followup_at: datetime | None
    completed_at: datetime | None
    source_agent: str | None
    created_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    save_id: UUID | None = None
    due_at: datetime | None = None
    scheduled_for: datetime | None = None
    assignee_id: UUID | None = None


class TaskUpdate(BaseModel):
    """Editing, accepting, rescheduling or dismissing a task."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["accepted", "skipped", "let_go"] | None = None
    scheduled_for: datetime | None = None
    due_at: datetime | None = None
    assignee_id: UUID | None = None


class TaskResponse(BaseModel):
    """The answer to 'Did you do it?'."""

    answer: Literal["done", "not_yet", "let_go"]
    reschedule_to: datetime | None = None


class TaskResponseOut(BaseModel):
    task: TaskOut
    next_step: TaskOut | None = None
