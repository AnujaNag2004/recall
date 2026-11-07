"""Flashcards, quizzes and the daily review queue."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import enforce_ai_limits
from app.core.permissions import require_role
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session
from app.guardrails.content import UNTRUSTED_SYSTEM_RULE, wrap_untrusted
from app.providers.base import ModelTier, ProviderError
from app.providers.registry import Providers, get_providers
from app.providers.structured import complete_structured
from app.services.srs import sm2

router = APIRouter(tags=["learn"])

Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
AiProviders = Annotated[Providers, Depends(get_providers)]
Limited = Annotated[None, Depends(enforce_ai_limits)]


class CardDraft(BaseModel):
    front: str
    back: str


class CardDrafts(BaseModel):
    cards: list[CardDraft]


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=6)
    answer_index: int


class Quiz(BaseModel):
    questions: list[QuizQuestion]


class FlashcardOut(BaseModel):
    id: UUID
    save_id: UUID | None
    front: str
    back: str
    due_at: datetime
    interval_days: int
    repetitions: int
    save_title: str | None = None


class ReviewBody(BaseModel):
    grade: int = Field(ge=0, le=5)


class ExplainBody(BaseModel):
    direction: Literal["simpler", "deeper"]


class ExplainOut(BaseModel):
    text: str


async def _save_content(session: AsyncSession, save_id: UUID) -> tuple[UUID, str]:
    row = (
        await session.execute(
            text(
                "select workspace_id, coalesce(raw_text, summary, '') as body "
                "from public.saves where id = :id and status = 'ready'"
            ),
            {"id": save_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Save not found or still processing")
    return row.workspace_id, row.body


def _busy() -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE, "The AI service is unavailable right now."
    )


@router.post("/saves/{save_id}/flashcards", status_code=status.HTTP_201_CREATED)
async def generate_flashcards(
    save_id: UUID, session: Session, providers: AiProviders, _limits: Limited
) -> list[FlashcardOut]:
    workspace_id, body = await _save_content(session, save_id)
    try:
        drafts = await complete_structured(
            providers.llm,
            "Write 3 to 8 flashcards testing the key ideas here. One fact per card, with a "
            f"specific question and a short answer.\n\n{wrap_untrusted(body[:20000])}",
            CardDrafts,
            system=UNTRUSTED_SYSTEM_RULE,
        )
    except ProviderError as error:
        raise _busy() from error
    created = []
    for card in drafts.cards[:8]:
        row = (
            await session.execute(
                text(
                    "insert into public.flashcards (save_id, workspace_id, front, back) "
                    "values (:s, :w, :f, :b) "
                    "returning id, save_id, front, back, due_at, interval_days, repetitions"
                ),
                {"s": save_id, "w": workspace_id, "f": card.front[:500], "b": card.back[:2000]},
            )
        ).one()
        created.append(FlashcardOut(**dict(row._mapping)))
    return created


@router.post("/saves/{save_id}/quiz")
async def generate_quiz(
    save_id: UUID, session: Session, providers: AiProviders, _limits: Limited
) -> Quiz:
    _, body = await _save_content(session, save_id)
    try:
        quiz = await complete_structured(
            providers.llm,
            "Write a quiz of 3 to 6 multiple choice questions on this content.\n\n"
            f"{wrap_untrusted(body[:20000])}",
            Quiz,
            system=UNTRUSTED_SYSTEM_RULE,
        )
    except ProviderError as error:
        raise _busy() from error
    # A question whose marked answer doesn't exist would just be wrong, so drop it.
    quiz.questions = [q for q in quiz.questions if 0 <= q.answer_index < len(q.options)]
    return quiz


@router.get("/workspaces/{workspace_id}/learn/queue")
async def review_queue(workspace_id: UUID, viewer: Viewer, session: Session) -> list[FlashcardOut]:
    rows = await session.execute(
        text(
            """
            select f.id, f.save_id, f.front, f.back, f.due_at, f.interval_days, f.repetitions,
                   s.title as save_title
            from public.flashcards f left join public.saves s on s.id = f.save_id
            where f.workspace_id = :w and f.due_at <= now()
            order by f.due_at limit 50
            """
        ),
        {"w": workspace_id},
    )
    return [FlashcardOut(**dict(row._mapping)) for row in rows]


@router.post("/flashcards/{card_id}/review")
async def review_card(card_id: UUID, body: ReviewBody, session: Session) -> FlashcardOut:
    card = (
        await session.execute(
            text("select ease, interval_days, repetitions from public.flashcards where id = :id"),
            {"id": card_id},
        )
    ).first()
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card not found")
    review = sm2(
        ease=card.ease,
        interval_days=card.interval_days,
        repetitions=card.repetitions,
        grade=body.grade,
        now=datetime.now(UTC),
    )
    row = (
        await session.execute(
            text(
                "update public.flashcards set ease = :e, interval_days = :i, repetitions = :r, "
                "due_at = :d where id = :id "
                "returning id, save_id, front, back, due_at, interval_days, repetitions"
            ),
            {
                "e": review.ease,
                "i": review.interval_days,
                "r": review.repetitions,
                "d": review.due_at,
                "id": card_id,
            },
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't review this")
    return FlashcardOut(**dict(row._mapping))


@router.post("/flashcards/{card_id}/explain")
async def explain_card(
    card_id: UUID, body: ExplainBody, session: Session, providers: AiProviders, _limits: Limited
) -> ExplainOut:
    card = (
        await session.execute(
            text("select front, back from public.flashcards where id = :id"), {"id": card_id}
        )
    ).first()
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card not found")
    style = (
        "more simply, as if to a beginner"
        if body.direction == "simpler"
        else "in more depth, with the reasoning behind it"
    )
    try:
        explanation = await providers.llm.complete(
            f"Explain this {style}.\n\nQuestion: {card.front}\nAnswer: {card.back}",
            tier=ModelTier.STRONG,
        )
    except ProviderError as error:
        raise _busy() from error
    return ExplainOut(text=explanation)
