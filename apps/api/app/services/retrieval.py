"""Hybrid retrieval: pgvector similarity and Postgres full-text search, fused with RRF.

Runs in the caller's session, so row-level security also applies to search.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.ingestion import vector_literal

RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    save_id: UUID
    save_title: str | None
    text: str
    start_ts: float | None
    score: float


@dataclass(frozen=True)
class SearchFilters:
    workspace_id: UUID
    save_id: UUID | None = None
    mode: str | None = None
    source_type: str | None = None
    since: datetime | None = None
    until: datetime | None = None


def rrf_fuse(rankings: list[list[UUID]], k: int = RRF_K) -> dict[UUID, float]:
    """Reciprocal Rank Fusion: rewards appearing high in any list, and in several."""
    scores: dict[UUID, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _filter_sql(filters: SearchFilters) -> tuple[str, dict[str, Any]]:
    clauses = ["c.workspace_id = :workspace", "s.status = 'ready'"]
    params: dict[str, Any] = {"workspace": filters.workspace_id}
    if filters.save_id:
        clauses.append("c.save_id = :save_id")
        params["save_id"] = filters.save_id
    if filters.mode:
        clauses.append("s.mode = cast(:mode as public.save_mode)")
        params["mode"] = filters.mode
    if filters.source_type:
        clauses.append("s.source_type = :source_type")
        params["source_type"] = filters.source_type
    if filters.since:
        clauses.append("s.created_at >= :since")
        params["since"] = filters.since
    if filters.until:
        clauses.append("s.created_at <= :until")
        params["until"] = filters.until
    return " and ".join(clauses), params


async def hybrid_search(
    session: AsyncSession,
    query: str,
    embedding: list[float],
    filters: SearchFilters,
    *,
    limit: int = 12,
    candidates: int = 30,
) -> list[RetrievedChunk]:
    where, params = _filter_sql(filters)
    base = f"from public.save_chunks c join public.saves s on s.id = c.save_id where {where}"
    vector_rows = await session.execute(
        text(
            f"select c.id {base} and c.embedding is not null "
            "order by c.embedding operator(extensions.<=>) cast(:embedding as extensions.vector) "
            "limit :candidates"
        ),
        {**params, "embedding": vector_literal(embedding), "candidates": candidates},
    )
    text_rows = await session.execute(
        text(
            f"select c.id {base} and c.tsv @@ websearch_to_tsquery('english', :query) "
            "order by ts_rank(c.tsv, websearch_to_tsquery('english', :query)) desc "
            "limit :candidates"
        ),
        {**params, "query": query, "candidates": candidates},
    )
    fused = rrf_fuse([[row.id for row in vector_rows], [row.id for row in text_rows]])
    top = sorted(fused, key=lambda chunk_id: fused[chunk_id], reverse=True)[:limit]
    if not top:
        return []
    rows = await session.execute(
        text(
            'select c.id, c.save_id, s.title, c."text", c.start_ts '
            "from public.save_chunks c join public.saves s on s.id = c.save_id "
            "where c.id = any(:ids)"
        ),
        {"ids": top},
    )
    by_id = {row.id: row for row in rows}
    return [
        RetrievedChunk(
            chunk_id,
            by_id[chunk_id].save_id,
            by_id[chunk_id].title,
            by_id[chunk_id].text,
            by_id[chunk_id].start_ts,
            fused[chunk_id],
        )
        for chunk_id in top
        if chunk_id in by_id
    ]
