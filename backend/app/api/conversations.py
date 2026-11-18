"""Conversation history endpoints (user-scoped, cross-user safe)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.comparison_schema import ConversationDetail, ConversationOut, MessageOut
from app.services import conversation_service

logger = logging.getLogger("shopmate.api.conversations")
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    rows = conversation_service.list_conversations(db, user.id)
    return [
        ConversationOut(
            id=c.id, title=c.title, created_at=c.created_at,
            updated_at=c.updated_at, message_count=count,
        )
        for c, count in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    conv = conversation_service.get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "conversation_not_found",
                    "message": "Conversation not found."},
        )
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages or []),
        messages=[MessageOut.model_validate(m) for m in conv.messages or []],
        context=conv.context or {},
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    ok = conversation_service.delete_conversation(db, user.id, conversation_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "conversation_not_found",
                    "message": "Conversation not found."},
        )
