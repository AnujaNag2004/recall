"""SQLAlchemy mappings onto the schema in `supabase/migrations/`.

Only tables the API already uses are mapped; later phases add theirs.
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class WorkspaceType(enum.StrEnum):
    personal = "personal"
    team = "team"


class WorkspaceRole(enum.StrEnum):
    viewer = "viewer"
    member = "member"
    admin = "admin"
    owner = "owner"

    @property
    def rank(self) -> int:
        return list(WorkspaceRole).index(self)


def _pg_enum(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_class, name=name, create_type=False, values_callable=lambda e: [m.value for m in e]
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    # auth.users isn't mapped, so this and user_id below carry no ForeignKey here.
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[WorkspaceType] = mapped_column(_pg_enum(WorkspaceType, "workspace_type"))
    owner_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    role: Mapped[WorkspaceRole] = mapped_column(_pg_enum(WorkspaceRole, "workspace_role"))

    workspace: Mapped[Workspace] = relationship()


class SaveMode(enum.StrEnum):
    life = "life"
    study = "study"
    work = "work"


class SaveStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class IntentSource(enum.StrEnum):
    user = "user"
    inferred = "inferred"


class Save(Base):
    __tablename__ = "saves"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    created_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[SaveMode | None] = mapped_column(_pg_enum(SaveMode, "save_mode"))
    status: Mapped[SaveStatus] = mapped_column(
        _pg_enum(SaveStatus, "save_status"), default=SaveStatus.pending
    )
    intent: Mapped[str | None] = mapped_column(Text)
    intent_source: Mapped[IntentSource | None] = mapped_column(
        _pg_enum(IntentSource, "intent_source")
    )
    summary: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list[str]] = mapped_column(JSONB, default=list)
    content_template: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stage: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranscriptSegmentRow(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    save_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    start_ts: Mapped[float] = mapped_column(Float)
    end_ts: Mapped[float | None] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    save_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(
        Enum("micro_action", "action_item", "checklist_item", name="task_type", create_type=False),
        default="action_item",
    )
    assignee_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        Enum(
            "suggested",
            "accepted",
            "done",
            "skipped",
            "let_go",
            name="task_status",
            create_type=False,
        ),
        default="accepted",
    )
    size: Mapped[str] = mapped_column(
        Enum("tiny", "small", "medium", name="task_size", create_type=False), default="small"
    )
    followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_agent: Mapped[str | None] = mapped_column(Text)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActionEvent(Base):
    __tablename__ = "action_events"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    event: Mapped[str] = mapped_column(
        Enum(
            "suggested",
            "accepted",
            "done",
            "skipped",
            "rescheduled",
            "let_go",
            name="action_event_type",
            create_type=False,
        )
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
