"""FastAPI application entry point."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.routers import health, me


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Recall API",
        description="Your AI memory and action layer for everything you save.",
        version="0.1.0",
    )
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
    app.include_router(api)
    return app


app = create_app()
