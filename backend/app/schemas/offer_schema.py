"""Public, normalized offer responses. Never includes provider credentials."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RetailOffer(BaseModel):
    product_id: str
    title: str
    merchant: str
    price: float
    currency: str = "INR"
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    deal_title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    availability: str = "unknown"
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    source_type: str
    is_sample_data: bool = False
    last_verified_at: datetime
    expires_at: Optional[datetime] = None


class OfferSearchResponse(BaseModel):
    query: str
    offers: list[RetailOffer] = Field(default_factory=list)
    providers_queried: list[str] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    as_of: datetime


class FeaturedOffer(BaseModel):
    id: str
    merchant: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    availability: str = "unknown"
    source_type: str
    is_sample_data: bool = False
    last_verified_at: datetime
    start_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class FeaturedOffersResponse(BaseModel):
    offers: list[FeaturedOffer] = Field(default_factory=list)
    providers_queried: list[str] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    as_of: datetime
