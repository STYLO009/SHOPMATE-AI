"""Conversation persistence & shopping memory.

The conversation `context` field stores the rolling structured understanding
produced by the query agent (budget, category, usage, requirements), so a
follow-up like "better battery life" updates the battery preference while
keeping the earlier budget and usage intact.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.conversation import Conversation, Message, SavedProduct, WatchlistEntry
from app.models.product import Product
from app.models.user import User

logger = logging.getLogger("shopmate.conversations")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_conversations(db: Session, user_id: str) -> list[tuple[Conversation, int]]:
    """All conversations for a user with message counts, newest first."""
    counts = dict(
        db.execute(
            select(Message.conversation_id, func.count(Message.id))
            .group_by(Message.conversation_id)
        ).all()
    )
    rows = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return [(c, counts.get(c.id, 0)) for c in rows]


def get_conversation(db: Session, user_id: str, conversation_id: str) -> Optional[Conversation]:
    """Fetch a conversation owned by the user (or None — cross-user safe)."""
    conv = db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .options(selectinload(Conversation.messages))
    )
    return conv


def create_conversation(db: Session, user_id: str, title: str = "New shopping research") -> Conversation:
    conv = Conversation(user_id=user_id, title=title[:255], context={})
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def delete_conversation(db: Session, user_id: str, conversation_id: str) -> bool:
    conv = get_conversation(db, user_id, conversation_id)
    if conv is None:
        return False
    db.delete(conv)
    db.commit()
    return True


def add_message(
    db: Session,
    conversation: Conversation,
    role: str,
    content: str,
    meta: Optional[dict[str, Any]] = None,
) -> Message:
    msg = Message(conversation_id=conversation.id, role=role, content=content,
                  meta=meta or {})
    db.add(msg)
    # Keep the rolling context + title in sync.
    if role == "assistant" and not conversation.title.startswith("Re: "):
        snippet = content.strip().split("\n")[0][:80]
        if snippet and conversation.title == "New shopping research":
            conversation.title = snippet
    conversation.updated_at = _now()
    db.commit()
    db.refresh(msg)
    return msg


def merge_context(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge a fresh query-agent understanding into the stored context.

    Scalars: new non-null values win (budget updates, new category).
    Lists (usage, requirements-ish lists): union, preserving order.
    Nested dicts (requirements): key-wise merge so "battery" survives while
    "ram_min" is upgraded.
    """
    merged = dict(old or {})
    for key, value in (new or {}).items():
        if value is None:
            continue
        if isinstance(value, dict):
            base = dict(merged.get(key) or {})
            base.update({k: v for k, v in value.items() if v is not None})
            merged[key] = base
        elif isinstance(value, list):
            base_list = list(merged.get(key) or [])
            for item in value:
                if item not in base_list:
                    base_list.append(item)
            merged[key] = base_list
        else:
            merged[key] = value
    return merged


def update_context(db: Session, conversation: Conversation,
                   new_context: dict[str, Any]) -> dict[str, Any]:
    conversation.context = merge_context(conversation.context or {}, new_context)
    conversation.updated_at = _now()
    db.commit()
    return conversation.context


def get_history(db: Session, conversation: Conversation, limit: int = 20) -> list[Message]:
    """Most recent messages, oldest-first (for prompt context)."""
    msgs = list(conversation.messages or [])
    return msgs[-limit:]


# --- saved products & watchlist --------------------------------------------

def save_product(db: Session, user_id: str, product_id: str,
                 note: Optional[str] = None) -> Optional[SavedProduct]:
    product = db.get(Product, product_id) or db.scalar(
        select(Product).where(Product.provider_product_id == product_id)
    )
    if product is None:
        return None
    existing = db.scalar(
        select(SavedProduct).where(
            SavedProduct.user_id == user_id, SavedProduct.product_id == product.id
        )
    )
    if existing:
        return existing
    entry = SavedProduct(user_id=user_id, product_id=product.id, note=note)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def unsave_product(db: Session, user_id: str, product_id: str) -> bool:
    product = db.get(Product, product_id) or db.scalar(
        select(Product).where(Product.provider_product_id == product_id)
    )
    if product is None:
        return False
    entry = db.scalar(
        select(SavedProduct).where(
            SavedProduct.user_id == user_id, SavedProduct.product_id == product.id
        )
    )
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True


def list_saved(db: Session, user_id: str) -> list[SavedProduct]:
    return db.scalars(
        select(SavedProduct)
        .where(SavedProduct.user_id == user_id)
        .options(selectinload(SavedProduct.product))
        .order_by(SavedProduct.created_at.desc())
    ).all()


def add_watchlist(db: Session, user_id: str, product_id: str,
                  target_price: Optional[float] = None) -> Optional[WatchlistEntry]:
    product = db.get(Product, product_id) or db.scalar(
        select(Product).where(Product.provider_product_id == product_id)
    )
    if product is None:
        return None
    existing = db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == user_id, WatchlistEntry.product_id == product.id
        )
    )
    if existing:
        if target_price is not None:
            existing.target_price = target_price
            db.commit()
            db.refresh(existing)
        return existing
    entry = WatchlistEntry(user_id=user_id, product_id=product.id,
                           target_price=target_price, last_price=product.price)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def remove_watchlist(db: Session, user_id: str, product_id: str) -> bool:
    product = db.get(Product, product_id) or db.scalar(
        select(Product).where(Product.provider_product_id == product_id)
    )
    if product is None:
        return False
    entry = db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == user_id, WatchlistEntry.product_id == product.id
        )
    )
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True


def list_watchlist(db: Session, user_id: str) -> list[WatchlistEntry]:
    return db.scalars(
        select(WatchlistEntry)
        .where(WatchlistEntry.user_id == user_id)
        .options(selectinload(WatchlistEntry.product))
        .order_by(WatchlistEntry.created_at.desc())
    ).all()
