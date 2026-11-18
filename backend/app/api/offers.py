"""Public read-only gateway for current affiliate offers."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query

from app.providers import get_registry
from app.providers.base import ProviderError
from app.schemas.offer_schema import (
    FeaturedOffer,
    FeaturedOffersResponse,
    OfferSearchResponse,
    RetailOffer,
)

router = APIRouter(prefix="/api/offers", tags=["public offers"])


def _price(value) -> Optional[float]:
    try:
        result = float(value)
        return result if result >= 0 and result < float("inf") else None
    except (TypeError, ValueError):
        return None


@router.get("/search", response_model=OfferSearchResponse)
async def search_offers(
    query: str = Query(min_length=1, max_length=200),
    category: Optional[str] = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=30),
):
    """Search live connected stores only. Sample listings are never returned here."""
    registry = get_registry()
    result = await registry.search_live(query=query, category=category, limit=limit)
    offers = []
    for product in result.products:
        specs = product.specifications or {}
        current = _price(product.price)
        original = _price(specs.get("list_price"))
        discount = _price(specs.get("discount_percentage"))
        if discount is None and current is not None and original and original > current:
            discount = round((original - current) / original * 100, 1)
        # This endpoint is for deals; do not label ordinary listings as discounts.
        if not ((discount is not None and discount > 0) or specs.get("offer_text")):
            continue
        if current is None:
            continue
        expires = specs.get("offer_expires_at")
        try:
            expires_at = datetime.fromisoformat(expires) if expires else None
        except (TypeError, ValueError):
            expires_at = None
        offers.append(RetailOffer(
            product_id=product.provider_product_id,
            title=product.title,
            merchant=product.merchant,
            price=current,
            currency=product.currency,
            original_price=original,
            discount_percentage=discount,
            deal_title=specs.get("offer_text"),
            category=product.category,
            description=product.description,
            availability=product.availability,
            product_url=product.product_url,
            image_url=product.image_url,
            source_type=product.source_type,
            is_sample_data=False,
            last_verified_at=product.last_verified_at,
            expires_at=expires_at,
        ))
    return OfferSearchResponse(
        query=query,
        offers=offers,
        providers_queried=[name for name in result.provider_name.split("+") if name and name != "none"],
        provider_errors=[result.error] if result.error else [],
        as_of=datetime.now(timezone.utc),
    )


@router.get("/featured", response_model=FeaturedOffersResponse)
async def featured_offers(
    deals_of_day: bool = True,
    limit: int = Query(default=24, ge=1, le=100),
):
    """Return Flipkart deals of the day, falling back to all active offers."""
    registry = get_registry()
    try:
        rows = await registry.flipkart.featured_offers(deals_of_day=deals_of_day)
        if deals_of_day and not rows:
            rows = await registry.flipkart.featured_offers(deals_of_day=False)
        offers = [FeaturedOffer.model_validate(row) for row in rows[:limit]]
        return FeaturedOffersResponse(
            offers=offers,
            providers_queried=["flipkart_affiliate"],
            as_of=datetime.now(timezone.utc),
        )
    except ProviderError as exc:
        return FeaturedOffersResponse(
            offers=[],
            providers_queried=[],
            provider_errors=[f"flipkart_affiliate: {exc.message}"],
            as_of=datetime.now(timezone.utc),
        )
