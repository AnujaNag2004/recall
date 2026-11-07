"""Splits content into overlapping chunks for embedding and retrieval."""

import re
from dataclasses import dataclass

from app.providers.base import TranscriptSegment

MAX_CHARS = 1500
OVERLAP_CHARS = 200


@dataclass(frozen=True)
class Chunk:
    text: str
    start_ts: float | None = None
    end_ts: float | None = None


def chunk_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> list[Chunk]:
    """Prefers breaking on paragraph, then sentence, boundaries."""
    text = text.strip()
    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            window = text[start:end]
            floor = max_chars // 2
            breaks = [window.rfind("\n\n"), *(m.end() for m in re.finditer(r"[.!?]\s", window))]
            best = max(breaks, default=-1)
            if best > floor:
                end = start + best
        piece = text[start:end].strip()
        if piece:
            chunks.append(Chunk(piece))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_transcript(segments: list[TranscriptSegment], max_chars: int = MAX_CHARS) -> list[Chunk]:
    """Keeps timestamps, so answers can link back to the moment in the video."""
    chunks: list[Chunk] = []
    current: list[TranscriptSegment] = []
    size = 0
    for segment in segments:
        if current and size + len(segment.text) > max_chars:
            chunks.append(_join(current))
            current, size = [], 0
        current.append(segment)
        size += len(segment.text) + 1
    if current:
        chunks.append(_join(current))
    return chunks


def _join(segments: list[TranscriptSegment]) -> Chunk:
    last = segments[-1]
    return Chunk(
        " ".join(s.text for s in segments),
        start_ts=segments[0].start,
        end_ts=last.end if last.end is not None else last.start,
    )
