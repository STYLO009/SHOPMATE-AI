"""Product / search / comparison schemas — the shared normalised contract."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: str
    provider_product_id: str
    title: str
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price: float
    currency: str = "INR"
    merchant: str
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    specifications: dict[str, Any] = Field(default_factory=dict)
    rating: Optional[float] = None
    review_count: Optional[int] = None
    availability: str = "unknown"
    source_type: str
    source_name: str = "unknown"
    is_sample_data: bool = False
    last_verified_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    category: Optional[str] = None
    budget_min: Optional[float] = Field(default=None, ge=0)
    budget_max: Optional[float] = Field(default=None, ge=0)
    limit: int = Field(default=12, ge=1, le=50)
    sort_by: str = Field(default="relevance")  # relevance | price_asc | price_desc | rating


class SearchResponse(BaseModel):
    products: list[ProductOut]
    total: int
    query: str
    category: Optional[str] = None
    providers_queried: list[str] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    is_sample_data: bool = False
    took_ms: int = 0


class CompareRequest(BaseModel):
    product_ids: list[str] = Field(min_length=2, max_length=4)


class SpecDifference(BaseModel):
    spec: str
    values: dict[str, str]
    better: Optional[str] = None  # product id that is better for this spec
    explanation: Optional[str] = None


class ComparisonResult(BaseModel):
    products: list[ProductOut]
    price_difference: Optional[float] = None
    cheapest_product_id: Optional[str] = None
    spec_differences: list[SpecDifference] = Field(default_factory=list)
    missing_specs: list[str] = Field(default_factory=list)
    stale_products: list[str] = Field(default_factory=list)
    verdict: Optional[str] = None
    best_value_id: Optional[str] = None
