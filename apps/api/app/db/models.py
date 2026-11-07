"""SQLAlchemy mappings onto the schema in `supabase/migrations/`.

Only tables the API already uses are mapped; later phases add theirs.
"""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Text
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
