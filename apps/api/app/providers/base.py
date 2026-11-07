"""Provider interfaces. Everything AI-related goes through these, so any provider can
be swapped through configuration, and tests can run without network access."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ModelTier(StrEnum):
    FAST = "fast"  # classification, extraction, tagging
    STRONG = "strong"  # answering, reflection


class ProviderError(Exception):
    """A provider call failed. It may work if retried later."""


class ProviderRateLimitedError(ProviderError):
    """The provider is throttling us; a fallback provider may still work."""


class ProviderNotConfiguredError(ProviderError):
    """A key or model ID is missing. Retrying can't help until settings change."""


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float | None
    text: str


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float = 0.0


class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tier: ModelTier = ModelTier.FAST,
        json_mode: bool = False,
    ) -> str: ...

    def stream(
        self, prompt: str, *, system: str | None = None, tier: ModelTier = ModelTier.STRONG
    ) -> AsyncIterator[str]: ...

    async def describe_media(self, data: bytes, mime_type: str, prompt: str) -> str: ...


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class TranscriptionProvider(Protocol):
    async def transcribe(
        self, data: bytes, filename: str, mime_type: str
    ) -> list[TranscriptSegment]: ...


class SearchProvider(Protocol):
    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]: ...
