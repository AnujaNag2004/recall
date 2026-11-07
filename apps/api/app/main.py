"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings, get_settings
from app.providers.registry import get_providers
from app.routers import health, home, me, saves, tasks
from app.services.storage import StorageError, get_file_store
from app.workers.handlers import build_handlers
from app.workers.queue import worker_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs background workers inside the API process, which keeps hosting free."""
    settings: Settings = app.state.settings
    tasks: list[asyncio.Task[None]] = []
    if settings.worker_enabled and settings.database_url:
        try:
            files = get_file_store()
        except StorageError:
            files = None
        handlers, on_failure = build_handlers(get_providers(), settings, files)
        tasks = [
            asyncio.create_task(worker_loop(handlers, settings, on_failure))
            for _ in range(settings.worker_concurrency)
        ]
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def _database_refused(request: Request, error: DBAPIError) -> JSONResponse:
    """Row-level security said no: that's a permissions answer, not a server fault."""
    if "row-level security" in str(error.orig) or "permission denied" in str(error.orig):
        return JSONResponse({"detail": "You don't have permission to do that"}, status_code=403)
    raise error


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        lifespan=lifespan,
        title="Recall API",
        description="Your AI memory and action layer for everything you save.",
        version="0.1.0",
    )
    app.state.settings = settings
    app.add_exception_handler(DBAPIError, _database_refused)  # type: ignore[arg-type]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)

    # Everything under /api/v1 requires a signed-in user.
    api = APIRouter(prefix="/api/v1")
    api.include_router(me.router)
    api.include_router(saves.router)
    api.include_router(tasks.router)
    api.include_router(home.router)
    app.include_router(api)
    return app


app = create_app()
