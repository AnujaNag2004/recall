"""Rate limits and the per-user daily AI cap, which keep free tiers alive."""

import logging
import time
from collections import defaultdict
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser, get_current_user
from app.db.session import service_session

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
_local_counts: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))


async def _hit(key: str, settings: Settings) -> int:
    """Counts a request. Uses Upstash when configured, so limits hold across instances."""
    window = int(time.time()) // WINDOW_SECONDS
    full_key = f"rate:{key}:{window}"
    if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.post(
                    f"{settings.upstash_redis_rest_url.rstrip('/')}/pipeline",
                    headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
                    json=[["INCR", full_key], ["EXPIRE", full_key, str(WINDOW_SECONDS * 2)]],
                )
            response.raise_for_status()
            return int(response.json()[0]["result"])
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:
            # A cache outage shouldn't take the product down; fall through to local counting.
            logger.warning("Rate limit store unavailable: %s", type(error).__name__)
    current_window, count = _local_counts[key]
    count = count + 1 if current_window == window else 1
    _local_counts[key] = (window, count)
    return count


async def enforce_rate_limit(
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    limits = [
        (f"user:{user.id}", settings.rate_limit_per_minute),
        (f"ip:{client_ip}", settings.rate_limit_per_minute * 3),
    ]
    for key, limit in limits:
        if await _hit(key, settings) > limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "You're going a bit fast. Please wait a moment and try again.",
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )


async def usage_today(user_id: object) -> int:
    async with service_session() as session:
        value = await session.scalar(
            text("select count from public.ai_usage where user_id = :u and day = current_date"),
            {"u": user_id},
        )
    return int(value or 0)


async def enforce_ai_limits(
    _rate: Annotated[None, Depends(enforce_rate_limit)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Atomically counts one AI action, refusing it once today's cap is reached."""
    async with service_session() as session:
        count = await session.scalar(
            text(
                """
                insert into public.ai_usage (user_id, day, count)
                values (:u, current_date, 1)
                on conflict (user_id, day) do update set count = public.ai_usage.count + 1
                where public.ai_usage.count < :cap
                returning count
                """
            ),
            {"u": user.id, "cap": settings.daily_ai_usage_cap},
        )
    if count is None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You've reached today's limit of {settings.daily_ai_usage_cap} AI actions. "
            "It resets tomorrow.",
        )
