"""Application settings, loaded from the environment (see the root `.env.example`)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The API runs from apps/api, so this finds the repo-root .env in local dev.
    # Real environment variables (containers, Render) always take precedence.
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    app_env: str = "development"

    # Comma-separated browser origins allowed by CORS. Never use "*" here:
    # authenticated requests from the frontend send credentials.
    cors_origins: str = "http://localhost:3000"

    # SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host:5432/db
    database_url: str | None = None

    # e.g. https://<project-ref>.supabase.co
    supabase_url: str | None = None
    # Only for older projects on shared-secret tokens; see app/core/security.py.
    supabase_jwt_secret: str | None = None
    # Server only. Used for Storage uploads and downloads.
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "saves"

    # Model IDs change often, so they're never hardcoded. `make check-ai` lists the
    # ones your keys can use.
    gemini_api_key: str | None = None
    gemini_fast_model: str | None = None
    gemini_strong_model: str | None = None
    gemini_embedding_model: str | None = None
    # Must match the vector(N) column in supabase/migrations.
    embedding_dim: int = 768
    groq_api_key: str | None = None
    groq_fast_model: str | None = None
    groq_strong_model: str | None = None
    groq_whisper_model: str | None = None
    tavily_api_key: str | None = None

    worker_enabled: bool = True
    worker_concurrency: int = 2
    worker_poll_seconds: float = 2.0
    job_max_attempts: int = 3
    max_upload_bytes: int = 25 * 1024 * 1024
    # Long sources are truncated before reaching a model, to stay within free tiers.
    max_content_chars: int = 200_000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supabase_issuer(self) -> str | None:
        return f"{self.supabase_url.rstrip('/')}/auth/v1" if self.supabase_url else None

    @property
    def supabase_jwks_url(self) -> str | None:
        return f"{self.supabase_issuer}/.well-known/jwks.json" if self.supabase_issuer else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
