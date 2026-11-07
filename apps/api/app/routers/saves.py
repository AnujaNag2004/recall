"""Capturing saves, reading them back, and streaming ingestion progress."""

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import Settings, get_settings
from app.core.permissions import require_role
from app.core.security import CurrentUser, get_current_user
from app.db.models import (
    IntentSource,
    Save,
    SaveMode,
    SaveStatus,
    Task,
    TranscriptSegmentRow,
    WorkspaceMember,
    WorkspaceRole,
)
from app.db.session import get_user_session, user_session
from app.schemas.saves import (
    RelatedSave,
    SaveCreate,
    SaveDetailOut,
    SaveList,
    SaveSummaryOut,
    SaveUpdate,
    TopicRef,
    TranscriptLine,
)
from app.schemas.tasks import ResourceOut, TaskOut
from app.services.safe_fetch import BlockedUrlError, FetchError, assert_public_url
from app.services.sources import UPLOAD_TYPES, detect_source_type, youtube_video_id
from app.services.storage import FileStore, StorageError, get_file_store

router = APIRouter(tags=["saves"])

Member = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.member))]
Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]

STREAM_POLL_SECONDS = 1.0
STREAM_MAX_SECONDS = 600
# Files whose real type can be confirmed from their first bytes.
MAGIC_BYTES = {
    "application/pdf": b"%PDF",
    "image/png": b"\x89PNG",
    "image/jpeg": b"\xff\xd8\xff",
}


def _optional_files() -> FileStore | None:
    """Reading a card shouldn't fail just because Storage isn't configured."""
    try:
        return get_file_store()
    except StorageError:
        return None


def _intent_source(intent: str | None) -> IntentSource | None:
    return IntentSource.user if intent else None


@router.post("/workspaces/{workspace_id}/saves", status_code=status.HTTP_201_CREATED)
async def create_save(
    workspace_id: UUID, body: SaveCreate, member: Member, user: User, session: Session
) -> SaveSummaryOut:
    url = body.url.strip() if body.url else None
    if url:
        if "://" not in url:
            url = f"https://{url}"
        try:
            await assert_public_url(url)
        except BlockedUrlError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        except FetchError:
            pass  # A DNS hiccup shouldn't block saving; the worker reports real failures.

    save = Save(
        id=uuid4(),
        workspace_id=workspace_id,
        created_by=user.id,
        source_url=url,
        source_type=detect_source_type(url) if url else "text",
        title=body.title,
        raw_text=None if url else body.text,
        intent=body.intent,
        intent_source=_intent_source(body.intent),
    )
    session.add(save)
    await session.flush()
    await session.refresh(save)
    return SaveSummaryOut.model_validate(save, from_attributes=True)


@router.post("/workspaces/{workspace_id}/saves/upload", status_code=status.HTTP_201_CREATED)
async def upload_save(
    workspace_id: UUID,
    file: UploadFile,
    member: Member,
    user: User,
    session: Session,
    settings: Annotated[Settings, Depends(get_settings)],
    files: Annotated[FileStore, Depends(get_file_store)],
) -> SaveSummaryOut:
    mime_type = (file.content_type or "").split(";")[0]
    kind = UPLOAD_TYPES.get(mime_type)
    if kind is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "That file type isn't supported. Try a PDF, image, audio or video file.",
        )
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        limit = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Files can be up to {limit} MB.")
    magic = MAGIC_BYTES.get(mime_type)
    if not data or (magic and not data.startswith(magic)):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "That file looks damaged.")

    save_id = uuid4()
    name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "upload")[-100:] or "upload"
    # The content type lives in the path, because the worker needs it to read the file.
    path = f"{workspace_id}/{save_id}/{mime_type.replace('/', '__')}/{name}"
    try:
        await files.upload(path, data, mime_type)
    except StorageError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "File storage is unavailable."
        ) from error

    save = Save(
        id=save_id,
        workspace_id=workspace_id,
        created_by=user.id,
        source_type=kind,
        title=file.filename[:200] if file.filename else None,
        storage_path=path,
    )
    session.add(save)
    await session.flush()
    await session.refresh(save)
    return SaveSummaryOut.model_validate(save, from_attributes=True)


@router.get("/workspaces/{workspace_id}/saves")
async def list_saves(
    workspace_id: UUID,
    viewer: Viewer,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: str | None = None,
    mode: SaveMode | None = None,
    source_type: str | None = None,
    save_status: Annotated[SaveStatus | None, Query(alias="status")] = None,
    topic: UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> SaveList:
    query = (
        select(Save)
        .where(Save.workspace_id == workspace_id)
        .order_by(Save.created_at.desc(), Save.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        query = query.where(Save.created_at < _parse_cursor(cursor))
    if mode:
        query = query.where(Save.mode == mode)
    if source_type:
        query = query.where(Save.source_type == source_type)
    if save_status:
        query = query.where(Save.status == save_status)
    if topic:
        query = query.where(
            Save.id.in_(
                select(text("save_id"))
                .select_from(text("public.save_topics"))
                .where(text("topic_id = :topic"))
            )
        ).params(topic=topic)
    if q and q.strip():
        pattern = f"%{q.strip().replace('%', '').replace('_', '')}%"
        query = query.where(
            or_(
                Save.title.ilike(pattern),
                Save.summary.ilike(pattern),
                Save.id.in_(
                    select(text("save_id"))
                    .select_from(text("public.save_chunks"))
                    .where(text("tsv @@ websearch_to_tsquery('english', :q)"))
                ),
            )
        ).params(q=q.strip())
    rows = list(await session.scalars(query))
    page = rows[:limit]
    return SaveList(
        items=[SaveSummaryOut.model_validate(s, from_attributes=True) for s in page],
        next_cursor=page[-1].created_at.isoformat() if len(rows) > limit else None,
    )


def _parse_cursor(cursor: str) -> datetime:
    try:
        return datetime.fromisoformat(cursor)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid cursor") from error


async def _get_save(session: AsyncSession, save_id: UUID) -> Save:
    # Row-level security decides visibility, so another workspace's save is simply absent.
    save = await session.scalar(select(Save).where(Save.id == save_id))
    if save is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Save not found")
    return save


@router.get("/saves/{save_id}")
async def get_save(
    save_id: UUID, session: Session, files: Annotated[FileStore | None, Depends(_optional_files)]
) -> SaveDetailOut:
    save = await _get_save(session, save_id)
    segments = await session.scalars(
        select(TranscriptSegmentRow)
        .where(TranscriptSegmentRow.save_id == save_id)
        .order_by(TranscriptSegmentRow.start_ts)
    )
    file_url = None
    if save.storage_path and files:
        try:
            file_url = await files.signed_url(save.storage_path)
        except StorageError:
            file_url = None  # The card still works without its original file.
    resources = await session.execute(
        text(
            """
            select e.id, e.name, e.type::text as entity_type, e.mention_ts, r.url, r.domain,
                   r.title, r.description, r.favicon_url, r.pricing::text as pricing, r.category,
                   r.confidence, coalesce(r.verified, false) as verified
            from public.entities e left join public.resources r on r.entity_id = e.id
            where e.save_id = :id
            order by coalesce(r.verified, false) desc, r.confidence desc nulls last, e.name
            """
        ),
        {"id": save_id},
    )
    topics = await session.execute(
        text(
            "select t.id, t.name from public.save_topics st "
            "join public.topics t on t.id = st.topic_id where st.save_id = :id order by t.name"
        ),
        {"id": save_id},
    )
    related = await session.execute(
        text(
            """
            select s.id, s.title, s.source_type
            from public.saves s
            where s.workspace_id = :workspace and s.id <> :id and s.status = 'ready'
              and s.id in (
                select st2.save_id from public.save_topics st
                join public.save_topics st2 on st2.topic_id = st.topic_id
                where st.save_id = :id
              )
            order by s.created_at desc limit 5
            """
        ),
        {"id": save_id, "workspace": save.workspace_id},
    )
    tasks = await session.scalars(
        select(Task).where(Task.save_id == save_id).order_by(Task.created_at)
    )
    summary = SaveSummaryOut.model_validate(save, from_attributes=True).model_dump()
    return SaveDetailOut(
        **summary,
        author=save.author,
        key_points=save.key_points,
        content_template=save.content_template,
        language=save.language,
        raw_text=save.raw_text,
        embed_youtube_id=youtube_video_id(save.source_url) if save.source_url else None,
        file_url=file_url,
        file_type=save.source_type if save.storage_path else None,
        transcript=[TranscriptLine(start=s.start_ts, end=s.end_ts, text=s.text) for s in segments],
        resources=[ResourceOut(**dict(row._mapping)) for row in resources],
        tasks=[TaskOut.model_validate(task, from_attributes=True) for task in tasks],
        topics=[TopicRef(**dict(row._mapping)) for row in topics],
        related=[RelatedSave(**dict(row._mapping)) for row in related],
    )


@router.patch("/saves/{save_id}")
async def update_save(save_id: UUID, body: SaveUpdate, session: Session) -> SaveSummaryOut:
    save = await _get_save(session, save_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(save, field, value)
    if "intent" in body.model_fields_set:
        save.intent_source = _intent_source(body.intent)
    await _flush_or_forbid(session)
    return SaveSummaryOut.model_validate(save, from_attributes=True)


async def _flush_or_forbid(session: AsyncSession) -> None:
    try:
        await session.flush()
    except StaleDataError as error:
        # Visible but not writable: row-level security matched no row for a viewer.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't edit this") from error


@router.post("/saves/{save_id}/retry")
async def retry_save(save_id: UUID, session: Session) -> SaveSummaryOut:
    save = await _get_save(session, save_id)
    if save.status != SaveStatus.failed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a failed save can be retried")
    save.status = SaveStatus.pending
    save.error = None
    await _flush_or_forbid(session)
    return SaveSummaryOut.model_validate(save, from_attributes=True)


@router.delete("/saves/{save_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_save(
    save_id: UUID, session: Session, files: Annotated[FileStore | None, Depends(_optional_files)]
) -> None:
    save = await _get_save(session, save_id)
    path = save.storage_path
    # RETURNING shows whether row-level security let the delete through. Without this a
    # viewer's refused delete would look successful, and remove the stored file too.
    deleted = await session.scalar(delete(Save).where(Save.id == save_id).returning(Save.id))
    if deleted is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't delete this")
    if path and files:
        # An orphaned private file is harmless, and shouldn't block deleting.
        with contextlib.suppress(StorageError):
            await files.delete(path)


@router.get("/saves/{save_id}/events")
async def save_events(save_id: UUID, user: User) -> StreamingResponse:
    """Progress as Server-Sent Events. Reads the row, so it works across restarts."""
    # Checked up front so a missing save gets a real 404, not an empty stream.
    async with user_session(user) as session:
        await _get_save(session, save_id)

    async def stream() -> AsyncIterator[str]:
        last: tuple[object, ...] | None = None
        elapsed = 0.0
        while elapsed < STREAM_MAX_SECONDS:
            async with user_session(user) as session:
                save = await session.scalar(select(Save).where(Save.id == save_id))
            if save is None:
                yield "event: deleted\ndata: {}\n\n"
                return
            current = (save.status, save.stage, save.error)
            if current != last:
                last = current
                payload = {"status": save.status.value, "stage": save.stage, "error": save.error}
                yield f"data: {json.dumps(payload)}\n\n"
            if save.status in {SaveStatus.ready, SaveStatus.failed}:
                return
            yield ": keep-alive\n\n"
            await asyncio.sleep(STREAM_POLL_SECONDS)
            elapsed += STREAM_POLL_SECONDS

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
