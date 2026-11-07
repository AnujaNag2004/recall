"""Records each agent run: always in our database, and in Langfuse when configured."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import service_session

logger = logging.getLogger(__name__)


async def _send_to_langfuse(
    settings: Settings, trace_id: str, graph: str, status: str, latency_ms: int
) -> None:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return
    event = {
        "id": str(uuid4()),
        "type": "trace-create",
        "timestamp": datetime.now(UTC).isoformat(),
        "body": {
            "id": trace_id,
            "name": graph,
            "metadata": {"status": status, "latency_ms": latency_ms},
        },
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{settings.langfuse_host.rstrip('/')}/api/public/ingestion",
                auth=(settings.langfuse_public_key, settings.langfuse_secret_key),
                json={"batch": [event]},
            )
    except httpx.HTTPError as error:
        # Observability must never be the reason a save fails.
        logger.warning("Langfuse unavailable: %s", type(error).__name__)


@asynccontextmanager
async def traced_run(graph: str, settings: Settings, save_id: UUID | None) -> AsyncIterator[None]:
    trace_id = str(uuid4())
    started = time.perf_counter()
    status, error_text = "succeeded", None
    try:
        yield
    except Exception as error:
        status, error_text = "failed", f"{type(error).__name__}: {error}"[:1000]
        raise
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        async with service_session() as session:
            await session.execute(
                text(
                    """
                    insert into public.agent_runs
                      (save_id, graph, status, trace_id, latency_ms, error)
                    values (:s, :g, cast(:st as public.agent_run_status), :t, :l, :e)
                    """
                ),
                {
                    "s": save_id,
                    "g": graph,
                    "st": status,
                    "t": trace_id,
                    "l": latency_ms,
                    "e": error_text,
                },
            )
        await _send_to_langfuse(settings, trace_id, graph, status, latency_ms)
