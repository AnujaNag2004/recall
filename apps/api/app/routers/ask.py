"""Ask Your Brain and per-save chat, streamed as Server-Sent Events."""

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.ask import (
    AskRequest,
    answer_prompt,
    build_retrieval_graph,
    build_sources,
    check_groundedness,
    used_citations,
)
from app.core.limits import enforce_ai_limits
from app.core.permissions import require_role
from app.core.security import CurrentUser, get_current_user
from app.db.models import WorkspaceMember, WorkspaceRole
from app.db.session import get_user_session, user_session
from app.providers.base import ProviderError
from app.providers.registry import Providers, get_providers
from app.services.retrieval import SearchFilters

router = APIRouter(tags=["ask"])

Viewer = Annotated[WorkspaceMember, Depends(require_role(WorkspaceRole.viewer))]
Session = Annotated[AsyncSession, Depends(get_user_session)]
User = Annotated[CurrentUser, Depends(get_current_user)]
AiProviders = Annotated[Providers, Depends(get_providers)]


class AskBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    mode: str | None = None
    source_type: str | None = None
    since: datetime | None = None
    until: datetime | None = None


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None


class ConversationOut(BaseModel):
    id: UUID
    title: str | None
    save_id: UUID | None
    updated_at: datetime


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    created_at: datetime


def _event(kind: str, **data: Any) -> str:
    return f"data: {json.dumps({'type': kind, **data}, default=str)}\n\n"


async def _start_conversation(
    user: CurrentUser,
    workspace_id: UUID,
    conversation_id: UUID | None,
    save_id: UUID | None,
    message: str,
) -> tuple[UUID, list[dict[str, str]]]:
    async with user_session(user) as session:
        history: list[dict[str, str]] = []
        if conversation_id:
            # Row-level security: someone else's conversation simply isn't found.
            found = await session.scalar(
                text("select id from public.conversations where id = :id and workspace_id = :w"),
                {"id": conversation_id, "w": workspace_id},
            )
            if found is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
            rows = await session.execute(
                text(
                    "select role::text as role, content from public.messages "
                    "where conversation_id = :id order by created_at"
                ),
                {"id": conversation_id},
            )
            history = [{"role": r.role, "content": r.content} for r in rows]
        else:
            conversation_id = await session.scalar(
                text(
                    "insert into public.conversations (workspace_id, user_id, save_id, title) "
                    "values (:w, :u, :s, :t) returning id"
                ),
                {"w": workspace_id, "u": user.id, "s": save_id, "t": message[:80]},
            )
        await session.execute(
            text(
                "insert into public.messages (conversation_id, role, content) "
                "values (:id, 'user', :c)"
            ),
            {"id": conversation_id, "c": message},
        )
    assert conversation_id is not None
    return conversation_id, history


async def _answer_stream(
    request: AskRequest, conversation_id: UUID, providers: Providers
) -> AsyncIterator[str]:
    yield _event("conversation", conversation_id=str(conversation_id))
    yield _event("status", message="Searching your saves")
    answer_parts: list[str] = []
    try:
        state = await build_retrieval_graph(providers).ainvoke({"request": request})
        sources = build_sources(state)
        yield _event("sources", sources=[source.public() for source in sources])
        yield _event("status", message="Writing the answer")
        prompt, system = answer_prompt(request, sources)
        async for token in providers.llm.stream(prompt, system=system):
            answer_parts.append(token)
            yield _event("token", text=token)
    except ProviderError as error:
        yield _event("error", message=_friendly(error))
        return

    answer = "".join(answer_parts).strip()
    citations = used_citations(answer, sources)
    check = await check_groundedness(providers, answer, sources)
    async with user_session(request.user) as session:
        message_id = await session.scalar(
            text(
                "insert into public.messages (conversation_id, role, content, citations) "
                "values (:id, 'assistant', :c, cast(:cites as jsonb)) returning id"
            ),
            {"id": conversation_id, "c": answer, "cites": json.dumps(citations, default=str)},
        )
        await session.execute(
            text("update public.conversations set updated_at = now() where id = :id"),
            {"id": conversation_id},
        )
    yield _event(
        "done",
        message_id=str(message_id),
        citations=citations,
        grounded=check.grounded,
        unsupported_claims=check.unsupported_claims,
    )


def _friendly(error: ProviderError) -> str:
    return "The AI service is busy or unavailable right now. Please try again in a moment."


def _sse(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/workspaces/{workspace_id}/ask")
async def ask(
    workspace_id: UUID,
    body: AskBody,
    viewer: Viewer,
    user: User,
    providers: AiProviders,
    _limits: Annotated[None, Depends(enforce_ai_limits)],
) -> StreamingResponse:
    conversation_id, history = await _start_conversation(
        user, workspace_id, body.conversation_id, None, body.message
    )
    request = AskRequest(
        question=body.message,
        user=user,
        history=history,
        filters=SearchFilters(
            workspace_id=workspace_id,
            mode=body.mode,
            source_type=body.source_type,
            since=body.since,
            until=body.until,
        ),
    )
    return _sse(_answer_stream(request, conversation_id, providers))


@router.post("/saves/{save_id}/chat")
async def chat_with_save(
    save_id: UUID,
    body: ChatBody,
    user: User,
    providers: AiProviders,
    _limits: Annotated[None, Depends(enforce_ai_limits)],
) -> StreamingResponse:
    async with user_session(user) as session:
        workspace_id = await session.scalar(
            text("select workspace_id from public.saves where id = :id"), {"id": save_id}
        )
    if workspace_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Save not found")
    conversation_id, history = await _start_conversation(
        user, workspace_id, body.conversation_id, save_id, body.message
    )
    request = AskRequest(
        question=body.message,
        user=user,
        history=history,
        allow_web=False,
        filters=SearchFilters(workspace_id=workspace_id, save_id=save_id),
    )
    return _sse(_answer_stream(request, conversation_id, providers))


@router.get("/workspaces/{workspace_id}/conversations")
async def list_conversations(
    workspace_id: UUID, viewer: Viewer, session: Session
) -> list[ConversationOut]:
    rows = await session.execute(
        text(
            "select id, title, save_id, updated_at from public.conversations "
            "where workspace_id = :w and save_id is null order by updated_at desc limit 50"
        ),
        {"w": workspace_id},
    )
    return [ConversationOut(**dict(row._mapping)) for row in rows]


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: UUID, session: Session) -> list[MessageOut]:
    found = await session.scalar(
        text("select id from public.conversations where id = :id"), {"id": conversation_id}
    )
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    rows = await session.execute(
        text(
            "select id, role::text as role, content, citations, created_at from public.messages "
            "where conversation_id = :id order by created_at"
        ),
        {"id": conversation_id},
    )
    return [MessageOut(**dict(row._mapping)) for row in rows]
