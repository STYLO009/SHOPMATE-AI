"""Agent 3 — Price Comparison Agent.

Compares merchant prices for a set of products and checks data freshness.
NEVER invents prices: every number comes from stored provider records, and
stale/missing data is reported explicitly.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.product_service import compare_products, get_products

logger = logging.getLogger("shopmate.agents.price")

STALE_AFTER_SECONDS = 24 * 3600


class PriceComparisonAgent:
    name = "price_comparison"

    async def run(
        self, db: Session, product_ids: list[str],
        products_hint: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        resolved_ids = list(product_ids)

        # Map provider ids / titles from the conversation to DB ids.
        if products_hint and len(resolved_ids) < 2:
            for p in products_hint:
                pid = p.get("product_id") or p.get("id")
                if pid and pid not in resolved_ids:
                    resolved_ids.append(pid)

        products = get_products(db, resolved_ids)
        if len(products) < 2:
            return {
                "comparison": None,
                "errors": ["Need at least two known products to compare prices."],
                "stale": [],
                "cheapest_id": None,
                "price_difference": None,
            }

        result = compare_products(db, [p.id for p in products])

        now = datetime.now(timezone.utc)
        stale = []
        for p in result.products:
            checked = p.last_verified_at
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=timezone.utc)
            if (now - checked).total_seconds() > STALE_AFTER_SECONDS:
                stale.append({
                    "product_id": p.id,
                    "title": p.title,
                    "last_verified_at": checked.isoformat(),
                })

        merchant_spread: dict[str, float] = {}
        for p in products:
            merchant_spread[p.merchant] = p.price

        errors: list[str] = []
        if stale:
            errors.append(
                f"{len(stale)} listing(s) have prices older than 24 hours — "
                "verify before purchasing."
            )
        if result.missing_specs:
            errors.append(
                "Some specifications are not published for every product."
            )

        return {
            "comparison": result.model_dump(mode="json"),
            "errors": errors,
            "stale": stale,
            "cheapest_id": result.cheapest_product_id,
            "price_difference": result.price_difference,
            "merchant_prices": merchant_spread,
            "best_value_id": result.best_value_id,
        }
