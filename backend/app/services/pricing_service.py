"""Pricing service: freshness checks and watchlist price updates.

Prices are always taken from provider responses (or recorded history) —
never synthesised. When a provider cannot be reached the entry keeps its
last known price and records the failed check time.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import WatchlistEntry
from app.models.product import PriceHistory, Product
from app.providers import get_registry
from app.utils.validators import is_valid_url

logger = logging.getLogger("shopmate.pricing")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_price(db: Session, product: Product, price: float,
                 availability: str = "unknown") -> None:
    db.add(PriceHistory(
        product_id=product.id,
        merchant=product.merchant,
        price=price,
        currency=product.currency,
        availability=availability,
    ))


def price_history(db: Session, product_id: str, limit: int = 30) -> list[PriceHistory]:
    return db.scalars(
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.recorded_at.desc())
        .limit(limit)
    ).all()


async def refresh_watchlist_prices(db: Session, user_id: str) -> list[dict]:
    """Re-check prices for a user's watchlist via the owning provider."""
    registry = get_registry()
    entries = db.scalars(
        select(WatchlistEntry).where(WatchlistEntry.user_id == user_id)
    ).all()

    results = []
    for entry in entries:
        product = db.get(Product, entry.product_id)
        if product is None:
            continue
        try:
            fresh = await registry.check_price(product.provider_product_id)
        except Exception as exc:
            logger.warning("price_check_failed product=%s error=%s",
                           product.provider_product_id, exc)
            fresh = None

        if fresh is not None:
            previous_price = product.price
            price_changed = abs(fresh.price - product.price) > 1e-9
            if price_changed:
                record_price(db, product, fresh.price, fresh.availability)
            product.price = fresh.price
            product.availability = fresh.availability
            product.last_verified_at = fresh.last_verified_at
            entry.last_price = fresh.price
            entry.check_count += 1
            entry.last_checked_at = _now()
            results.append({
                "product_id": product.id,
                "title": product.title,
                "price": fresh.price,
                "previous_price": previous_price,
                "changed": price_changed,
                "target_reached": (
                    entry.target_price is not None and fresh.price <= entry.target_price
                ),
                "status": "ok",
            })
        else:
            entry.last_checked_at = _now()
            entry.check_count += 1
            results.append({
                "product_id": product.id,
                "title": product.title,
                "price": entry.last_price or product.price,
                "changed": False,
                "target_reached": False,
                "status": "unavailable",
            })

    db.commit()
    return results


def validate_product_url(url: Optional[str]) -> bool:
    """Reject non-http(s) or malformed product URLs."""
    return is_valid_url(url)
