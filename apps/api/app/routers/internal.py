"""Scheduled jobs, triggered by GitHub Actions. Protected by a shared secret, not a user."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.demo import reset_demo_password
from app.db.session import service_session

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)

CRON_JOBS = {
    "hourly": ["just_in_time_recall", "adapt_tasks"],
    "weekly": ["weekly_insights", "link_health"],
}


class EnqueuedOut(BaseModel):
    enqueued: list[str]


def verify_cron_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> None:
    # An unset secret must lock this route, not open it.
    expected = settings.cron_secret
    if not expected or not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid cron secret")


@router.post(
    "/cron/{job}",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_cron_secret)],
)
async def trigger_cron(
    job: str, settings: Annotated[Settings, Depends(get_settings)]
) -> EnqueuedOut:
    """Only queues the work: a slow job must not keep the scheduler's request open."""
    types = CRON_JOBS.get(job)
    if types is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown job")
    if job == "hourly":
        await reset_demo_password(settings)
    async with service_session() as session:
        for job_type in types:
            # Skipped if one is still pending, so a backlog can't pile up.
            await session.execute(
                text(
                    """
                    insert into public.jobs (type)
                    select :t where not exists (
                      select 1 from public.jobs
                      where type = :t and status in ('queued', 'running')
                    )
                    """
                ),
                {"t": job_type},
            )
    return EnqueuedOut(enqueued=types)
