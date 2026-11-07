"""Agents that run on a schedule: recall, adapting tasks, weekly insights, link health."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.session import service_session, user_session
from app.guardrails.content import UNTRUSTED_SYSTEM_RULE, wrap_untrusted
from app.providers.base import ModelTier, ProviderError
from app.providers.registry import Providers
from app.providers.structured import complete_structured
from app.services.link_verification import VERIFIED_THRESHOLD
from app.services.metrics import compute_metrics, load_save_facts, pattern_facts
from app.services.retrieval import SearchFilters, hybrid_search
from app.services.safe_fetch import BlockedUrlError, FetchError, safe_fetch

logger = logging.getLogger(__name__)

SKIPS_BEFORE_ASKING = 2
TONE_RULES = (
    "Be honest and kind, like a thoughtful friend. Never shame, scold or guilt the person. "
    "Base every claim only on the numbers given. Suggesting they save less is welcome when "
    "the numbers support it."
)


class Briefing(BaseModel):
    summary: str = Field(description="Two sentences on why these saves matter for this")


class SmallerStep(BaseModel):
    title: str = Field(description="An even smaller version, doable in under five minutes")


class DigestSection(BaseModel):
    topic: str
    summary: str
    action: str = Field(description="One small thing to do about it")


class Digest(BaseModel):
    headline: str
    sections: list[DigestSection]


class Reflection(BaseModel):
    insights: list[str] = Field(description="Two or three honest, kind observations")
    challenge: str | None = Field(default=None, description="At most one suggested challenge")


async def _members(session: AsyncSession) -> list[Any]:
    rows = await session.execute(text("select workspace_id, user_id from public.workspace_members"))
    return list(rows)


async def run_just_in_time_recall(providers: Providers) -> int:
    """For anything in the next 24 hours, find related saves and make a card."""
    async with service_session() as session:
        events = list(
            await session.execute(
                text(
                    """
                    select e.id, e.workspace_id, e.user_id, e.title, e.starts_at
                    from public.calendar_events e
                    where e.starts_at between now() and now() + interval '24 hours'
                      and not exists (
                        select 1 from public.recall_cards c
                        where c.event_id = e.id and c.user_id = e.user_id
                      )
                    limit 100
                    """
                )
            )
        )
    created = 0
    for event in events:
        try:
            created += await _card_for_event(providers, event)
        except ProviderError as error:
            logger.warning("Skipped a recall card: %s", error)
    return created


async def _card_for_event(providers: Providers, event: Any) -> int:
    embedding = (await providers.embeddings.embed([event.title]))[0]
    # Searched as the user, so a card can only ever include what they can already see.
    async with user_session(CurrentUser(event.user_id, None)) as session:
        chunks = await hybrid_search(
            session, event.title, embedding, SearchFilters(event.workspace_id), limit=6
        )
    if not chunks:
        return 0
    save_ids = list(dict.fromkeys(chunk.save_id for chunk in chunks))[:4]
    excerpts = "\n\n".join(wrap_untrusted(chunk.text[:500]) for chunk in chunks[:4])
    briefing = await complete_structured(
        providers.llm,
        f"Coming up: {event.title!r}. In two sentences, say why these saved notes matter for "
        f"it.\n\n{excerpts}",
        Briefing,
        system=UNTRUSTED_SYSTEM_RULE,
    )
    async with service_session() as session:
        await session.execute(
            text(
                """
                insert into public.recall_cards
                  (workspace_id, user_id, event_id, title, body, save_ids, expires_at)
                values (:w, :u, :e, :t, :b, :s, :x)
                on conflict (user_id, event_id) do nothing
                """
            ),
            {
                "w": event.workspace_id,
                "u": event.user_id,
                "e": event.id,
                "t": f"Before {event.title}",
                "b": briefing.summary,
                "s": save_ids,
                "x": event.starts_at + timedelta(hours=1),
            },
        )
    return 1


async def run_adapt_tasks(providers: Providers) -> int:
    """After two 'not yet's, propose a smaller version instead of nagging about the same one."""
    async with service_session() as session:
        tasks = list(
            await session.execute(
                text(
                    """
                    select id, workspace_id, save_id, title, assignee_id
                    from public.tasks
                    where status = 'accepted' and skip_count >= :skips and size <> 'tiny'
                    limit 50
                    """
                ),
                {"skips": SKIPS_BEFORE_ASKING},
            )
        )
    adapted = 0
    for task in tasks:
        try:
            smaller = await complete_structured(
                providers.llm,
                f"This task keeps getting put off: {task.title!r}. Propose a much smaller "
                "version of it.",
                SmallerStep,
            )
        except ProviderError as error:
            logger.warning("Skipped adapting a task: %s", error)
            continue
        async with service_session() as session:
            await session.execute(
                text(
                    """
                    update public.tasks
                    set title = :title, size = 'tiny', skip_count = 0
                    where id = :id
                    """
                ),
                {"title": smaller.title[:300], "id": task.id},
            )
        adapted += 1
    return adapted


async def _week_of_saves(session: AsyncSession, workspace_id: UUID, creator: UUID) -> list[Any]:
    rows = await session.execute(
        text(
            """
            select s.title, s.summary, coalesce(t.name, 'Other') as topic
            from public.saves s
            left join public.save_topics st on st.save_id = s.id
            left join public.topics t on t.id = st.topic_id
            where s.workspace_id = :w and s.status = 'ready'
              and s.created_at >= now() - interval '7 days'
              and s.created_by = :u
            limit 60
            """
        ),
        {"w": workspace_id, "u": creator},
    )
    return list(rows)


async def run_weekly_insights(providers: Providers) -> int:
    today = datetime.now(UTC).date()
    period_start = today - timedelta(days=today.weekday())
    async with service_session() as session:
        members = await _members(session)
    created = 0
    for member in members:
        try:
            created += await _insights_for(providers, member, period_start)
        except ProviderError as error:
            logger.warning("Skipped weekly insights: %s", error)
    return created


async def _insights_for(providers: Providers, member: Any, period_start: Any) -> int:
    async with service_session() as session:
        week = await _week_of_saves(session, member.workspace_id, member.user_id)
        facts = pattern_facts(await load_save_facts(session, member.workspace_id))
        metrics = await compute_metrics(session, member.workspace_id)
    if facts["score"]["total"] == 0 and not week:
        return 0  # Nothing happened, so there's nothing honest to say.

    digest = None
    if week:
        listing = "\n".join(
            f"- [{row.topic}] {row.title}: {(row.summary or '')[:200]}" for row in week
        )
        digest = await complete_structured(
            providers.llm,
            "Write this person's weekly digest of what they saved, grouped by topic, with one "
            f"small action per topic.\n\n{wrap_untrusted(listing)}",
            Digest,
            system=UNTRUSTED_SYSTEM_RULE,
            tier=ModelTier.STRONG,
        )
    reflection = await complete_structured(
        providers.llm,
        "Write this person's weekly reflection on their save-versus-action patterns: two or "
        f"three insights and at most one challenge. Numbers: {facts}. Streak: "
        f"{metrics['streak_days']} days.",
        Reflection,
        system=TONE_RULES,
        tier=ModelTier.STRONG,
    )
    reflection.insights = reflection.insights[:3]
    async with service_session() as session:
        for kind, value in (("weekly_digest", digest), ("reflection", reflection)):
            if value is None:
                continue
            await session.execute(
                text(
                    """
                    insert into public.insights (workspace_id, user_id, period_start, kind, content)
                    values (:w, :u, :p, cast(:k as public.insight_kind), cast(:c as jsonb))
                    on conflict (workspace_id, user_id, period_start, kind)
                    do update set content = excluded.content
                    """
                ),
                {
                    "w": member.workspace_id,
                    "u": member.user_id,
                    "p": period_start,
                    "k": kind,
                    "c": value.model_dump_json(),
                },
            )
    return 1


async def run_link_health() -> int:
    """Re-checks stored links, and unverifies any that have died."""
    async with service_session() as session:
        resources = list(
            await session.execute(
                text(
                    """
                    select id, url, confidence from public.resources
                    order by last_checked_at asc nulls first limit 100
                    """
                )
            )
        )
    dead = 0
    for resource in resources:
        try:
            await safe_fetch(resource.url, max_bytes=1024 * 1024)
            alive = True
        except (FetchError, BlockedUrlError):
            alive = False
            dead += 1
        async with service_session() as session:
            await session.execute(
                text(
                    """
                    update public.resources
                    set last_checked_at = now(), verified = :verified
                    where id = :id
                    """
                ),
                {
                    "id": resource.id,
                    "verified": alive and resource.confidence >= VERIFIED_THRESHOLD,
                },
            )
    return dead
