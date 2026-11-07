"""Stand-ins for external AI services, so tests are fast and need no keys."""

import json
from typing import Any

from app.providers.base import (
    ModelTier,
    ProviderRateLimitedError,
    SearchResult,
    TranscriptSegment,
)
from app.providers.registry import Providers


class FakeLLM:
    """Answers by matching a keyword in the prompt; records every prompt it sees."""

    name = "fake"

    def __init__(self, answers: dict[str, Any] | None = None) -> None:
        self.answers: dict[str, Any] = {
            "Classify this": {"mode": "study", "content_template": "study", "language": "en"},
            "Summarize this": {
                "title": "Graphs explained",
                "tldr": "A short tour of graph algorithms.",
                "key_points": ["BFS finds shortest paths.", "DFS explores deeply."],
            },
            "List every specific": {"entities": []},
            "Extract ": {"actions": [{"title": "Solve one graph problem"}]},
            "Assign this content": {"topics": ["Algorithms"]},
            "Why would someone": {"intent": "learn"},
            "smallest concrete first step": {
                "title": "Read one problem statement",
                "size": "tiny",
                "hours_from_now": 4,
            },
            **(answers or {}),
        }
        self.prompts: list[str] = []

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tier: ModelTier = ModelTier.FAST,
        json_mode: bool = False,
    ) -> str:
        self.prompts.append(prompt)
        for key, value in self.answers.items():
            if key in prompt:
                return value if isinstance(value, str) else json.dumps(value)
        return "{}" if json_mode else "ok"

    async def describe_media(self, data: bytes, mime_type: str, prompt: str) -> str:
        return "A photo of a whiteboard listing graph algorithms and their running times."


class FakeEmbeddings:
    def __init__(self, dim: int = 768) -> None:
        self.dim = dim
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [_vector(text, self.dim) for text in texts]


def _vector(text: str, dim: int) -> list[float]:
    """Deterministic, and similar for texts sharing words, so retrieval can be tested."""
    values = [0.0] * dim
    for word in text.lower().split():
        values[hash_word(word) % dim] += 1.0
    norm = sum(v * v for v in values) ** 0.5 or 1.0
    return [v / norm for v in values]


def hash_word(word: str) -> int:
    return sum((i + 1) * ord(c) for i, c in enumerate(word))


class FakeTranscription:
    async def transcribe(
        self, data: bytes, filename: str, mime_type: str
    ) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(0, 5, "Welcome to this voice note about graphs."),
            TranscriptSegment(5, 9, "Breadth first search visits neighbours first."),
        ]


class FakeSearch:
    def __init__(self, results: dict[str, list[SearchResult]] | None = None) -> None:
        self.results = results or {}
        self.queries: list[str] = []

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        for key, value in self.results.items():
            if key.lower() in query.lower():
                return value[:max_results]
        return []


class ThrottledLLM(FakeLLM):
    name = "throttled"

    async def complete(self, *args: Any, **kwargs: Any) -> str:
        raise ProviderRateLimitedError("slow down")


def fake_providers(**overrides: Any) -> Providers:
    return Providers(
        llm=overrides.get("llm", FakeLLM()),
        embeddings=overrides.get("embeddings", FakeEmbeddings()),
        transcription=overrides.get("transcription", FakeTranscription()),
        search=overrides.get("search", FakeSearch()),
    )
