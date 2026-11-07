"""A Postgres-backed job queue, running inside the API process.

`FOR UPDATE SKIP LOCKED` lets several workers share the table safely. A job whose
worker died (free hosting puts servers to sleep mid-job) goes back in the queue once
it has been "running" for too long.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.core.config import Settings
from app.db.session import service_session
from app.providers.base import ProviderNotConfiguredError

logger = logging.getLogger(__name__)

STALE_AFTER = "10 minutes"


class PermanentJobError(Exception):
    """Retrying can't help. The message is safe to show the user."""


@dataclass(frozen=True)
class Job:
    id: UUID
    type: str
    payload: dict[str, Any]
    attempts: int


Handler = Callable[[Job], Awaitable[None]]
FailureHandler = Callable[[Job, str], Awaitable[None]]


async def claim_job() -> Job | None:
    async with service_session() as session:
        row = (
            await session.execute(
                text(
                    f"""
                    update public.jobs set status = 'running', attempts = attempts + 1
                    where id = (
                      select id from public.jobs
                      where (status = 'queued' and run_after <= now())
                         or (status = 'running' and updated_at < now() - interval '{STALE_AFTER}')
                      order by run_after
                      for update skip locked
                      limit 1
                    )
                    returning id, type, payload, attempts
                    """
                )
            )
        ).first()
    if row is None:
        return None
    payload = row.payload if isinstance(row.payload, dict) else json.loads(row.payload)
    return Job(row.id, row.type, payload, row.attempts)


async def complete_job(job: Job) -> None:
    async with service_session() as session:
        await session.execute(
            text("update public.jobs set status = 'succeeded', last_error = null where id = :id"),
            {"id": job.id},
        )


async def fail_job(job: Job, error: str, *, retry_in_seconds: int | None) -> None:
    async with service_session() as session:
        if retry_in_seconds is None:
            await session.execute(
                text("update public.jobs set status = 'failed', last_error = :e where id = :id"),
                {"id": job.id, "e": error[:2000]},
            )
        else:
            await session.execute(
                text(
                    "update public.jobs set status = 'queued', last_error = :e, "
                    "run_after = now() + make_interval(secs => :delay) where id = :id"
                ),
                {"id": job.id, "e": error[:2000], "delay": retry_in_seconds},
            )


async def run_one_job(
    handlers: dict[str, Handler],
    settings: Settings,
    on_final_failure: FailureHandler | None = None,
) -> bool:
    """Runs the next job, if any. Returns whether there was one."""
    job = await claim_job()
    if job is None:
        return False
    try:
        handler = handlers.get(job.type)
        if handler is None:
            raise PermanentJobError(f"No handler for job type {job.type}")
        await handler(job)
    except (PermanentJobError, ProviderNotConfiguredError) as error:
        logger.warning("Job %s failed permanently: %s", job.id, error)
        await fail_job(job, str(error), retry_in_seconds=None)
        if on_final_failure:
            await on_final_failure(job, str(error))
    except Exception as error:
        logger.exception("Job %s failed on attempt %s", job.id, job.attempts)
        if job.attempts >= settings.job_max_attempts:
            await fail_job(job, repr(error), retry_in_seconds=None)
            if on_final_failure:
                await on_final_failure(job, "Something went wrong processing this. Please retry.")
        else:
            await fail_job(job, repr(error), retry_in_seconds=30 * 2 ** (job.attempts - 1))
    else:
        await complete_job(job)
    return True


async def worker_loop(
    handlers: dict[str, Handler],
    settings: Settings,
    on_final_failure: FailureHandler | None = None,
) -> None:
    while True:
        try:
            had_job = await run_one_job(handlers, settings, on_final_failure)
        except asyncio.CancelledError:
            raise
        except Exception:
            # The database may be briefly unreachable; keep the worker alive.
            logger.exception("Worker iteration failed")
            had_job = False
        if not had_job:
            await asyncio.sleep(settings.worker_poll_seconds)
