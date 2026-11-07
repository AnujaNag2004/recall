"""The knowledge graph and weekly insights."""

import statistics
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.core.security import CurrentUser, get_current_user
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session

router = APIRouter(tags=["insights"])

Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]

MIN_BLIND_SPOT_SAVES = 3


class GraphNode(BaseModel):
    id: UUID
    name: str
    save_count: int
    done_count: int
    obsession: bool
    blind_spot: bool


class GraphEdge(BaseModel):
    source: UUID
    target: UUID
    relation: str


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class InsightOut(BaseModel):
    id: UUID
    kind: str
    period_start: date
    content: dict[str, Any]


def classify_topics(counts: list[tuple[int, int]]) -> list[tuple[bool, bool]]:
    """(obsession, blind spot) per topic. An obsession stands well above the typical topic;
    a blind spot is something saved repeatedly with nothing ever done."""
    median = statistics.median([saved for saved, _ in counts]) if counts else 0
    return [
        (saved >= 3 and saved >= 2 * median, saved >= MIN_BLIND_SPOT_SAVES and done == 0)
        for saved, done in counts
    ]


@router.get("/workspaces/{workspace_id}/graph")
async def get_graph(workspace_id: UUID, viewer: Viewer, session: Session) -> GraphOut:
    rows = list(
        await session.execute(
            text(
                """
                select t.id, t.name, count(distinct st.save_id) as save_count,
                       count(distinct task.save_id) filter (where task.status = 'done')
                         as done_count
                from public.topics t
                left join public.save_topics st on st.topic_id = t.id
                left join public.tasks task on task.save_id = st.save_id
                where t.workspace_id = :w
                group by t.id, t.name
                having count(distinct st.save_id) > 0
                order by save_count desc limit 200
                """
            ),
            {"w": workspace_id},
        )
    )
    flags = classify_topics([(r.save_count, r.done_count) for r in rows])
    nodes = [
        GraphNode(
            id=row.id,
            name=row.name,
            save_count=row.save_count,
            done_count=row.done_count,
            obsession=obsession,
            blind_spot=blind_spot,
        )
        for row, (obsession, blind_spot) in zip(rows, flags, strict=True)
    ]
    edges = await session.execute(
        text(
            """
            select e.from_topic as source, e.to_topic as target, e.relation
            from public.topic_edges e
            join public.topics t on t.id = e.from_topic
            where t.workspace_id = :w
            """
        ),
        {"w": workspace_id},
    )
    ids = {node.id for node in nodes}
    return GraphOut(
        nodes=nodes,
        edges=[
            GraphEdge(**dict(row._mapping))
            for row in edges
            if row.source in ids and row.target in ids
        ],
    )


@router.get("/workspaces/{workspace_id}/insights")
async def list_insights(workspace_id: UUID, viewer: Viewer, session: Session) -> list[InsightOut]:
    rows = await session.execute(
        text(
            "select id, kind::text as kind, period_start, content from public.insights "
            "where workspace_id = :w order by period_start desc, kind limit 20"
        ),
        {"w": workspace_id},
    )
    return [InsightOut(**dict(row._mapping)) for row in rows]
