"""Unauthenticated health endpoints, used by the host and the keep-warm ping."""

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.db.session import check_database

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


def get_database_check() -> Callable[[], Awaitable[None]]:
    return check_database


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. Deliberately does not touch the database."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(
    response: Response,
    database_check: Annotated[Callable[[], Awaitable[None]], Depends(get_database_check)],
) -> dict[str, str]:
    """Readiness: the API can reach its database."""
    try:
        await database_check()
    except Exception:
        # Log the cause server-side only: connection errors can contain the host.
        logger.exception("Readiness check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}
