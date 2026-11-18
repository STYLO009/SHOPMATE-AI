"""Chat / agent / recommendation schemas."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None


class ProductCard(BaseModel):
    """Product embedded in a chat message."""

    product_id: str
    title: str
    brand: Optional[str] = None
    merchant: str
    price: float
    currency: str = "INR"
    image_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    source_type: str
    is_sample_data: bool = False
    product_url: Optional[str] = None
    reason: Optional[str] = None
    score: Optional[float] = None


class RankedProduct(BaseModel):
    product: ProductCard
    final_score: float
    factor_scores: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class AgentTraceStep(BaseModel):
    agent: str
    status: Literal["ok", "error", "skipped"] = "ok"
    detail: Optional[str] = None
    took_ms: int = 0


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    reply: str
    intent: Optional[str] = None
    products: list[ProductCard] = Field(default_factory=list)
    ranked: list[RankedProduct] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    trace: list[AgentTraceStep] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    llm_mode: str = "unknown"
    created_at: datetime


class RecommendationRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    category: Optional[str] = None
    budget_max: Optional[float] = Field(default=None, ge=0)
    usage: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=5, ge=1, le=20)


class RecommendationResponse(BaseModel):
    ranked: list[RankedProduct]
    weights: dict[str, float]
    llm_mode: str = "unknown"
    notes: list[str] = Field(default_factory=list)


class ReviewAnalyzeRequest(BaseModel):
    product_id: Optional[str] = None
    query: Optional[str] = None


class ReviewTheme(BaseModel):
    theme: str
    sentiment: Literal["positive", "negative", "neutral"]
    mentions: int
    example_quote: Optional[str] = None


class ReviewAnalysisResponse(BaseModel):
    product_id: Optional[str] = None
    product_title: Optional[str] = None
    review_count: int = 0
    average_rating: Optional[float] = None
    positive_themes: list[ReviewTheme] = Field(default_factory=list)
    negative_themes: list[ReviewTheme] = Field(default_factory=list)
    recurring_complaints: list[str] = Field(default_factory=list)
    summary: str
    reliability_concerns: list[str] = Field(default_factory=list)
    is_sample_data: bool = False
    llm_mode: str = "unknown"
