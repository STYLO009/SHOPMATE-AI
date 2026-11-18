"""Chat endpoint — runs the LangGraph shopping research workflow.

Supports:
- JSON response (default) with product cards, ranking, trace and follow-ups.
- SSE streaming (?stream=true) emitting progress + the final payload.
- Conversation persistence + rolling shopping memory (prior_context).
"""

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.graph.shopping_graph import run_research
from app.models.user import User
from app.schemas.chat_schema import ChatRequest, ChatResponse, ProductCard
from app.services import conversation_service

logger = logging.getLogger("shopmate.api.chat")
router = APIRouter(prefix="/api", tags=["chat"])


def _to_card(p: dict) -> ProductCard:
    """Map a normalised product dict (state['products']) to a ProductCard."""
    return ProductCard(
        product_id=p.get("product_id") or p.get("id") or "",
        title=p.get("title", ""),
        brand=p.get("brand"),
        merchant=p.get("merchant", "unknown"),
        price=float(p.get("price") or 0),
        currency=p.get("currency", "INR"),
        image_url=p.get("image_url"),
        rating=p.get("rating"),
        review_count=p.get("review_count"),
        source_type=p.get("source_type", "unknown"),
        is_sample_data=bool(p.get("is_sample_data")),
        product_url=p.get("product_url"),
    )


def _build_response(state: dict, conversation_id: str, message_id: str,
                    created_at) -> ChatResponse:
    products = [
        _to_card(p) if isinstance(p, dict) else p
        for p in (state.get("products") or [])[:8]
    ]
    return ChatResponse(
        conversation_id=conversation_id,
        message_id=message_id,
        reply=state.get("final_response") or "",
        intent=state.get("intent"),
        products=products,
        ranked=state.get("ranked") or [],
        suggested_followups=state.get("suggested_followups") or [],
        trace=state.get("trace") or [],
        errors=state.get("errors") or [],
        llm_mode=state.get("llm_mode") or "unknown",
        created_at=created_at,
    )


async def run_chat_turn(payload: ChatRequest, user: User,
                        db: Session) -> ChatResponse:
    """One complete research turn: memory load → graph → persist reply.

    Shared by the JSON endpoint and the SSE stream so both behave identically.
    """
    conversation = None
    if payload.conversation_id:
        conversation = conversation_service.get_conversation(
            db, user.id, payload.conversation_id
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "conversation_not_found",
                        "message": "Conversation not found."},
            )
    else:
        title = payload.message.strip().split("\n")[0][:60] or "New shopping research"
        conversation = conversation_service.create_conversation(db, user.id, title=title)

    # Conversation-level memory: recent turns + rolling structured context.
    history = [
        {"role": m.role, "content": m.content}
        for m in conversation_service.get_history(db, conversation, limit=12)
    ]
    prior_context = dict(conversation.context or {})
    conversation_service.add_message(db, conversation, "user", payload.message)

    # --- run the agentic graph ---
    try:
        state = await run_research(
            query=payload.message,
            user_id=user.id,
            conversation_id=conversation.id,
            history=history,
            prior_context=prior_context,
            db=db,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("chat_graph_failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "research_failed",
                    "message": "The research workflow failed. Please retry."},
        )

    # --- persist assistant reply + rolling memory ---
    assistant_msg = conversation_service.add_message(
        db, conversation, "assistant",
        state.get("final_response") or "",
        meta={
            "intent": state.get("intent"),
            "products": state.get("products") or [],
            "ranked": state.get("ranked") or [],
            "suggested_followups": state.get("suggested_followups") or [],
            "trace": state.get("trace") or [],
            "errors": state.get("errors") or [],
            "llm_mode": state.get("llm_mode"),
            "is_sample_data": state.get("is_sample_data"),
        },
    )
    conversation_service.update_context(db, conversation,
                                        state.get("understanding") or {})
    # Keep product anchors so follow-ups ("is it worth it?") stay on target.
    u = state.get("understanding") or {}
    if u.get("target_product_ids"):
        conversation_service.update_context(db, conversation, {
            "target_product_ids": u["target_product_ids"],
        })
    elif state.get("products"):
        ids = [p.get("id") for p in (state.get("products") or [])][:4]
        conversation_service.update_context(db, conversation, {
            "last_product_ids": ids,
        })

    return _build_response(state, conversation.id, assistant_msg.id,
                           assistant_msg.created_at)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    stream: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run one research turn. Backend auth is validated independently of UI."""
    if stream:
        return await _stream_chat(payload, user, db)
    return await run_chat_turn(payload, user, db)


async def _stream_chat(payload: ChatRequest, user: User,
                       db: Session) -> StreamingResponse:
    """SSE stream: emits progress events then the complete final payload."""

    async def event_gen() -> AsyncIterator[str]:
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

        yield sse("status", {"stage": "started", "message": "Research started"})
        try:
            response = await run_chat_turn(payload, user, db)
            yield sse("progress", {"stage": "complete", "trace": response.trace})
            yield sse("message", response.model_dump(mode="json"))
            yield sse("done", {"ok": True})
        except HTTPException as exc:
            yield sse("error", exc.detail)
            yield sse("done", {"ok": False})
        except Exception as exc:
            logger.exception("stream_chat_failed")
            yield sse("error", {"code": "stream_failed", "message": str(exc)})
            yield sse("done", {"ok": False})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
