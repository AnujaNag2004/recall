"""The Save-to-Action score. Computed from the event log, in plain code, never a model.

A save counts as "acted on" once any of its tasks is done. Saves someone chose to let
go of leave the total, because the score measures follow-through on what they still
intend to do: letting go honestly should never count against them.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class SaveFacts:
    save_id: UUID
    intent: str | None
    created_at: datetime
    task_statuses: tuple[str, ...]


def is_acted_on(save: SaveFacts) -> bool:
    return "done" in save.task_statuses


def is_let_go(save: SaveFacts) -> bool:
    statuses = save.task_statuses
    return bool(statuses) and all(status == "let_go" for status in statuses)


def compute_score(saves: list[SaveFacts]) -> dict[str, int | float]:
    counted = [save for save in saves if not is_let_go(save)]
    acted = sum(is_acted_on(save) for save in counted)
    total = len(counted)
    return {"acted": acted, "total": total, "ratio": round(acted / total, 3) if total else 0.0}


def compute_streak(done_days: set[date], today: date) -> int:
    """Consecutive days with something done. Today not being done yet doesn't break it."""
    day = today if today in done_days else today - timedelta(days=1)
    streak = 0
    while day in done_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def by_category(saves: list[SaveFacts]) -> list[dict[str, Any]]:
    saved: Counter[str] = Counter()
    acted: Counter[str] = Counter()
    for save in saves:
        if is_let_go(save):
            continue
        category = save.intent or "unsorted"
        saved[category] += 1
        acted[category] += is_acted_on(save)
    return [
        {"category": name, "saved": count, "acted": acted[name]}
        for name, count in saved.most_common()
    ]


def weekly_trend(saves: list[SaveFacts], today: date, weeks: int = 8) -> list[dict[str, Any]]:
    """The running score at the end of each recent week."""
    points = []
    for offset in range(weeks - 1, -1, -1):
        end = today - timedelta(weeks=offset)
        included = [save for save in saves if save.created_at.date() <= end]
        score = compute_score(included)
        points.append({"week_ending": end.isoformat(), "ratio": score["ratio"], **score})
    return points


async def load_save_facts(session: AsyncSession, workspace_id: UUID) -> list[SaveFacts]:
    rows = await session.execute(
        text(
            """
            select s.id, s.intent, s.created_at,
                   coalesce(array_agg(t.status::text) filter (where t.id is not null), '{}')
                     as statuses
            from public.saves s
            left join public.tasks t on t.save_id = s.id and t.status <> 'suggested'
            where s.workspace_id = :w and s.status = 'ready'
            group by s.id
            """
        ),
        {"w": workspace_id},
    )
    return [SaveFacts(r.id, r.intent, r.created_at, tuple(r.statuses)) for r in rows]


async def compute_metrics(session: AsyncSession, workspace_id: UUID) -> dict[str, Any]:
    saves = await load_save_facts(session, workspace_id)
    today = datetime.now(UTC).date()
    done_rows = await session.execute(
        text(
            """
            select distinct (e."at" at time zone 'utc')::date as day
            from public.action_events e join public.tasks t on t.id = e.task_id
            where t.workspace_id = :w and e.event = 'done'
            """
        ),
        {"w": workspace_id},
    )
    changed = await session.execute(
        text(
            """
            select t.id, t.title, t.completed_at, t.save_id, s.title as save_title
            from public.tasks t left join public.saves s on s.id = t.save_id
            where t.workspace_id = :w and t.status = 'done'
            order by t.completed_at desc nulls last limit 10
            """
        ),
        {"w": workspace_id},
    )
    return {
        "score": compute_score(saves),
        "streak_days": compute_streak({row.day for row in done_rows}, today),
        "categories": by_category(saves),
        "trend": weekly_trend(saves, today),
        "changed": [
            {
                "task_id": row.id,
                "title": row.title,
                "completed_at": row.completed_at,
                "save_id": row.save_id,
                "save_title": row.save_title,
            }
            for row in changed
        ],
    }


def pattern_facts(saves: list[SaveFacts]) -> dict[str, Any]:
    """What the reflection agent is allowed to reason from: counts, not guesses."""
    groups: dict[str, list[SaveFacts]] = defaultdict(list)
    for save in saves:
        groups[save.intent or "unsorted"].append(save)
    no_action = [
        (len(items), name)
        for name, items in groups.items()
        if not any(is_acted_on(item) for item in items)
    ]
    largest = max(no_action, default=None)
    return {
        "score": compute_score(saves),
        "categories": by_category(saves),
        "largest_group_with_no_action": (
            {"category": largest[1], "saved": largest[0]} if largest else None
        ),
    }
