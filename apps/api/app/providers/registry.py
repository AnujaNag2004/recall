"""Builds the configured providers. Tests and evals inject fakes through `Providers`."""

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    SearchProvider,
    TranscriptionProvider,
)
from app.providers.http_providers import FallbackLLM, GeminiProvider, GroqProvider, TavilyProvider


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    embeddings: EmbeddingProvider
    transcription: TranscriptionProvider
    search: SearchProvider


@lru_cache
def get_providers() -> Providers:
    settings = get_settings()
    gemini = GeminiProvider(settings)
    groq = GroqProvider(settings)
    return Providers(
        llm=FallbackLLM([gemini, groq]),
        embeddings=gemini,
        transcription=groq,
        search=TavilyProvider(settings),
    )
