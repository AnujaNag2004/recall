"""Persists ingestion results. Runs as a background worker, outside row-level security."""

import itertools
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.ingestion import (
    Classification,
    Entity,
    IngestionState,
    MicroCommitment,
    PlannedAction,
    Summary,
    vector_literal,
)
from app.core.config import Settings
from app.db.models import IntentSource, Save, SaveMode, SaveStatus, TranscriptSegmentRow
from app.db.session import service_session
from app.providers.registry import Providers
from app.services.chunking import Chunk
from app.services.content import FetchedContent, fetch_link, fetch_youtube, read_upload
from app.services.link_verification import VerifiedResource
from app.services.storage import FileStore


async def _log_event(session: AsyncSession, task_id: UUID, event: str) -> None:
    await session.execute(
        text(
            "insert into public.action_events (task_id, event) "
            "values (:t, cast(:e as public.action_event_type))"
        ),
        {"t": task_id, "e": event},
    )


class SqlIngestionStore:
    async def set_stage(self, save_id: UUID, stage: str) -> None:
        async with service_session() as session:
            await session.execute(
                update(Save)
                .where(Save.id == save_id)
                .values(status=SaveStatus.processing, stage=stage, error=None)
            )

    async def save_content(self, save_id: UUID, content: FetchedContent, text_: str) -> None:
        async with service_session() as session:
            save = await session.get_one(Save, save_id)
            save.raw_text = text_
            save.title = save.title or content.title
            save.author = save.author or content.author
            save.thumbnail_url = save.thumbnail_url or content.thumbnail_url
            # Clear earlier results, so a retry can't leave duplicates.
            await session.execute(
                delete(TranscriptSegmentRow).where(TranscriptSegmentRow.save_id == save_id)
            )
            if content.transcript:
                await session.execute(
                    insert(TranscriptSegmentRow),
                    [
                        {"save_id": save_id, "start_ts": s.start, "end_ts": s.end, "text": s.text}
                        for s in content.transcript
                    ],
                )

    async def save_classification(self, save_id: UUID, value: Classification) -> None:
        async with service_session() as session:
            save = await session.get_one(Save, save_id)
            save.mode = save.mode or SaveMode(value.mode)
            save.content_template = value.content_template
            save.language = value.language

    async def save_summary(self, save_id: UUID, value: Summary, keep_title: bool) -> None:
        async with service_session() as session:
            save = await session.get_one(Save, save_id)
            save.summary = value.tldr
            save.key_points = value.key_points
            if not keep_title:
                save.title = value.title

    async def save_chunks(
        self, save_id: UUID, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        async with service_session() as session:
            workspace_id = await session.scalar(select(Save.workspace_id).where(Save.id == save_id))
            await session.execute(
                text("delete from public.save_chunks where save_id = :id"), {"id": save_id}
            )
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                await session.execute(
                    text(
                        "insert into public.save_chunks "
                        '(save_id, workspace_id, chunk_index, "text", start_ts, end_ts, embedding)'
                        " values (:save, :workspace, :index, :body, :start, :end,"
                        " cast(:embedding as extensions.vector))"
                    ),
                    {
                        "save": save_id,
                        "workspace": workspace_id,
                        "index": index,
                        "body": chunk.text,
                        "start": chunk.start_ts,
                        "end": chunk.end_ts,
                        "embedding": vector_literal(embedding),
                    },
                )

    async def clear_derived(self, save_id: UUID) -> None:
        """A retry starts clean. Tasks someone already accepted are theirs, and stay."""
        async with service_session() as session:
            await session.execute(
                text("delete from public.entities where save_id = :id"), {"id": save_id}
            )
            await session.execute(
                text("delete from public.tasks where save_id = :id and status = 'suggested'"),
                {"id": save_id},
            )

    async def save_entity(
        self, save_id: UUID, entity: Entity, resource: VerifiedResource | None
    ) -> None:
        async with service_session() as session:
            entity_id = await session.scalar(
                text(
                    "insert into public.entities (save_id, name, type, mention_ts, context) "
                    "values (:save, :name, cast(:type as public.entity_type), :ts, :context) "
                    "returning id"
                ),
                {
                    "save": save_id,
                    "name": entity.name[:200],
                    "type": entity.type,
                    "ts": entity.mention_seconds,
                    "context": entity.context[:500],
                },
            )
            if resource is None:
                return
            await session.execute(
                text(
                    "insert into public.resources (entity_id, save_id, url, domain, title, "
                    "description, favicon_url, pricing, category, confidence, verified, "
                    "last_checked_at) values (:entity, :save, :url, :domain, :title, :description,"
                    " :favicon, cast(:pricing as public.resource_pricing), :category, :confidence,"
                    " :verified, now())"
                ),
                {
                    "entity": entity_id,
                    "save": save_id,
                    "url": resource.url,
                    "domain": resource.domain,
                    "title": resource.title,
                    "description": resource.description,
                    "favicon": resource.favicon_url,
                    "pricing": resource.pricing,
                    "category": resource.category,
                    "confidence": resource.confidence,
                    "verified": resource.verified,
                },
            )

    async def save_action(self, save_id: UUID, action: PlannedAction) -> None:
        due = None
        if action.due:
            try:
                due = datetime.combine(
                    date.fromisoformat(action.due[:10]), datetime.min.time(), UTC
                )
            except ValueError:
                due = None  # The model's date is a suggestion; a bad one isn't worth failing on.
        async with service_session() as session:
            workspace_id = await session.scalar(select(Save.workspace_id).where(Save.id == save_id))
            # Owners are matched by name against the workspace's own members, never trusted.
            assignee = None
            if action.owner:
                assignee = await session.scalar(
                    text(
                        "select p.user_id from public.profiles p "
                        "join public.workspace_members m on m.user_id = p.user_id "
                        "where m.workspace_id = :w and lower(p.name) like lower(:name) limit 1"
                    ),
                    {"w": workspace_id, "name": f"%{action.owner.strip()[:80]}%"},
                )
            task_id = await session.scalar(
                text(
                    "insert into public.tasks (workspace_id, save_id, title, description, type, "
                    "assignee_id, due_at, status, size, source_agent) values (:w, :s, :title, "
                    ":description, cast(:type as public.task_type), :assignee, :due, 'suggested', "
                    "'small', 'action_extractor') returning id"
                ),
                {
                    "w": workspace_id,
                    "s": save_id,
                    "title": action.title[:300],
                    "description": action.description,
                    "type": action.type,
                    "assignee": assignee,
                    "due": due,
                },
            )
            await _log_event(session, task_id, "suggested")

    async def existing_topics(self, save_id: UUID) -> list[str]:
        async with service_session() as session:
            names = await session.scalars(
                text(
                    "select t.name from public.topics t join public.saves s "
                    "on s.workspace_id = t.workspace_id where s.id = :id order by t.name"
                ),
                {"id": save_id},
            )
            return list(names)

    async def save_topics(self, save_id: UUID, topics: list[str]) -> None:
        async with service_session() as session:
            workspace_id = await session.scalar(select(Save.workspace_id).where(Save.id == save_id))
            await session.execute(
                text("delete from public.save_topics where save_id = :id"), {"id": save_id}
            )
            ids = []
            for name in {t.strip()[:80] for t in topics if t.strip()}:
                topic_id = await session.scalar(
                    text(
                        "insert into public.topics (workspace_id, name) values (:w, :name) "
                        "on conflict (workspace_id, name) do update set name = excluded.name "
                        "returning id"
                    ),
                    {"w": workspace_id, "name": name},
                )
                ids.append(topic_id)
                await session.execute(
                    text("insert into public.save_topics (save_id, topic_id) values (:s, :t)"),
                    {"s": save_id, "t": topic_id},
                )
            # Topics appearing on the same save are related; the graph draws these edges.
            for first, second in itertools.combinations(sorted(ids, key=str), 2):
                await session.execute(
                    text(
                        "insert into public.topic_edges (from_topic, to_topic, relation) "
                        "values (:a, :b, 'related') on conflict do nothing"
                    ),
                    {"a": first, "b": second},
                )

    async def save_inferred_intent(self, save_id: UUID, intent: str) -> None:
        async with service_session() as session:
            save = await session.get_one(Save, save_id)
            save.intent = intent
            save.intent_source = IntentSource.inferred

    async def save_micro_commitment(
        self, save_id: UUID, value: MicroCommitment, scheduled_for: datetime
    ) -> None:
        async with service_session() as session:
            save = await session.get_one(Save, save_id)
            task_id = await session.scalar(
                text(
                    "insert into public.tasks (workspace_id, save_id, title, type, assignee_id, "
                    "scheduled_for, status, size, source_agent) values (:w, :s, :title, "
                    "'micro_action', :assignee, :when, 'suggested', "
                    "cast(:size as public.task_size), 'micro_commitment') returning id"
                ),
                {
                    "w": save.workspace_id,
                    "s": save_id,
                    "title": value.title[:300],
                    "assignee": save.created_by,
                    "when": scheduled_for,
                    "size": value.size,
                },
            )
            await _log_event(session, task_id, "suggested")

    async def finish(self, save_id: UUID) -> None:
        async with service_session() as session:
            await session.execute(
                update(Save)
                .where(Save.id == save_id)
                .values(
                    status=SaveStatus.ready, stage=None, error=None, processed_at=datetime.now(UTC)
                )
            )

    async def fail(self, save_id: UUID, message: str) -> None:
        async with service_session() as session:
            await session.execute(
                update(Save)
                .where(Save.id == save_id)
                .values(status=SaveStatus.failed, stage=None, error=message)
            )


class SourceReader:
    def __init__(self, providers: Providers, settings: Settings, files: FileStore | None) -> None:
        self._providers = providers
        self._settings = settings
        self._files = files

    async def read(self, state: IngestionState) -> FetchedContent:
        if state.get("storage_path"):
            return await self._read_stored(state)
        url = state.get("source_url")
        if url:
            if state["source_type"] == "youtube":
                return await fetch_youtube(url)
            return await fetch_link(url, self._settings, self._providers.llm)
        return FetchedContent(text=state.get("raw_text") or "")

    async def _read_stored(self, state: IngestionState) -> FetchedContent:
        if self._files is None:
            raise RuntimeError("File storage isn't configured")
        path = str(state["storage_path"])
        # Stored as <workspace>/<save>/<mime-with-dash>/<name>; see routers/saves.py.
        mime_type = path.split("/")[2].replace("__", "/")
        return await read_upload(
            await self._files.download(path),
            mime_type,
            path.rsplit("/", 1)[-1],
            self._providers.llm,
            self._providers.transcription,
        )
