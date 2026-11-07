from uuid import UUID

from pydantic import BaseModel

from app.db.models import WorkspaceRole, WorkspaceType


class UserOut(BaseModel):
    id: UUID
    email: str | None
    name: str | None
    avatar_url: str | None
    timezone: str


class WorkspaceOut(BaseModel):
    id: UUID
    name: str
    type: WorkspaceType
    role: WorkspaceRole


class MeOut(BaseModel):
    user: UserOut
    workspaces: list[WorkspaceOut]
