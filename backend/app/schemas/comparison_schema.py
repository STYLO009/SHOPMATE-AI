"""Conversation / watchlist / comparison-history response schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.chat_schema import ProductCard


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class SavedProductOut(BaseModel):
    id: str
    product: ProductCard
    note: Optional[str] = None
    created_at: datetime


class WatchlistEntryOut(BaseModel):
    id: str
    product: ProductCard
    target_price: Optional[float] = None
    last_price: Optional[float] = None
    last_checked_at: Optional[datetime] = None
    check_count: int = 0
    created_at: datetime


class WatchlistCreateRequest(BaseModel):
    product_id: str
    target_price: Optional[float] = Field(default=None, ge=0)


class ComparisonHistoryOut(BaseModel):
    id: str
    product_ids: list[str]
    products: list[ProductCard]
    verdict: Optional[str] = None
    created_at: datetime
