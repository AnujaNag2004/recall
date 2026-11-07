"""Connects job types to the code that runs them."""

from uuid import UUID

from sqlalchemy import select

from app.agents.ingestion import IngestionDeps, build_ingestion_graph
from app.agents.scheduled import (
    run_adapt_tasks,
    run_just_in_time_recall,
    run_link_health,
    run_weekly_insights,
)
from app.core.config import Settings
from app.db.models import IntentSource, Save
from app.db.session import service_session
from app.providers.registry import Providers
from app.services.content import UnreadableSourceError
from app.services.ingestion_store import SourceReader, SqlIngestionStore
from app.services.storage import FileStore
from app.services.tracing import traced_run
from app.workers.queue import FailureHandler, Handler, Job, PermanentJobError


def build_handlers(
    providers: Providers, settings: Settings, files: FileStore | None
) -> tuple[dict[str, Handler], FailureHandler]:
    store = SqlIngestionStore()
    graph = build_ingestion_graph(
        IngestionDeps(providers, store, SourceReader(providers, settings, files), settings)
    )

    async def ingest_save(job: Job) -> None:
        save_id = UUID(job.payload["save_id"])
        async with service_session() as session:
            save = await session.scalar(select(Save).where(Save.id == save_id))
            if save is None:
                return  # Deleted while it was queued.
            state = {
                "save_id": save.id,
                "source_type": save.source_type,
                "source_url": save.source_url,
                "storage_path": save.storage_path,
                "raw_text": save.raw_text,
                "user_title": save.title,
                "intent": save.intent if save.intent_source == IntentSource.user else None,
            }
        try:
            async with traced_run("ingestion", settings, save_id):
                await graph.ainvoke(state)
        except UnreadableSourceError as error:
            raise PermanentJobError(str(error)) from error

    async def on_final_failure(job: Job, message: str) -> None:
        if job.type == "ingest_save":
            await store.fail(UUID(job.payload["save_id"]), message)

    async def just_in_time_recall(job: Job) -> None:
        await run_just_in_time_recall(providers)

    async def adapt_tasks(job: Job) -> None:
        await run_adapt_tasks(providers)

    async def weekly_insights(job: Job) -> None:
        await run_weekly_insights(providers)

    async def link_health(job: Job) -> None:
        await run_link_health()

    return {
        "ingest_save": ingest_save,
        "just_in_time_recall": just_in_time_recall,
        "adapt_tasks": adapt_tasks,
        "weekly_insights": weekly_insights,
        "link_health": link_health,
    }, on_final_failure
