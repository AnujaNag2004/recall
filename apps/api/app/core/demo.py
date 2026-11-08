"""Keeps the shared demo account usable for everyone who tries it."""

import logging
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser, get_current_user
from app.db.session import service_session

logger = logging.getLogger(__name__)


def is_demo(user: CurrentUser, settings: Settings) -> bool:
    if not settings.demo_email or not user.email:
        return False
    return user.email.strip().lower() == settings.demo_email.strip().lower()


def forbid_demo(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """For actions that would change the account for the next visitor, or reach outside it."""
    if is_demo(user, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not available in the demo account")


async def reset_demo_password(settings: Settings) -> None:
    """Undoes a visitor changing the shared password. Failure is logged, never raised."""
    if not (
        settings.demo_email
        and settings.demo_password
        and settings.supabase_url
        and settings.supabase_service_role_key
    ):
        return
    async with service_session() as session:
        user_id = await session.scalar(
            text("select id from auth.users where lower(email) = lower(:e)"),
            {"e": settings.demo_email},
        )
    if user_id is None:
        return
    key = settings.supabase_service_role_key
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.put(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {key}", "apikey": key},
                json={"password": settings.demo_password},
            )
        if response.status_code >= 400:
            logger.warning("Demo password reset returned HTTP %s", response.status_code)
    except httpx.HTTPError:
        logger.warning("Demo password reset could not reach Supabase")
