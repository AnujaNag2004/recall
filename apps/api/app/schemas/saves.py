from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.db.models import SaveMode, SaveStatus
from app.schemas.tasks import ResourceOut, TaskOut


class SaveCreate(BaseModel):
    url: str | None = Field(default=None, max_length=2048)
    text: str | None = Field(default=None, max_length=200_000)
    title: str | None = Field(default=None, max_length=200)
    intent: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def exactly_one_source(self) -> "SaveCreate":
        if bool(self.url and self.url.strip()) == bool(self.text and self.text.strip()):
            raise ValueError("Provide either a link or some text")
        return self


class SaveUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    mode: SaveMode | None = None
    intent: str | None = Field(default=None, max_length=40)


class SaveSummaryOut(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str | None
    source_url: str | None
    source_type: str
    thumbnail_url: str | None
    mode: SaveMode | None
    status: SaveStatus
    stage: str | None
    error: str | None
    summary: str | None
    intent: str | None
    created_at: datetime


class TranscriptLine(BaseModel):
    start: float
    end: float | None
    text: str


class TopicRef(BaseModel):
    id: UUID
    name: str


class RelatedSave(BaseModel):
    id: UUID
    title: str | None
    source_type: str


class SaveDetailOut(SaveSummaryOut):
    author: str | None
    key_points: list[str]
    content_template: str | None
    language: str | None
    raw_text: str | None
    embed_youtube_id: str | None
    file_url: str | None
    file_type: str | None
    transcript: list[TranscriptLine]
    resources: list[ResourceOut]
    tasks: list[TaskOut]
    topics: list[TopicRef]
    related: list[RelatedSave]


class SaveList(BaseModel):
    items: list[SaveSummaryOut]
    next_cursor: str | None
