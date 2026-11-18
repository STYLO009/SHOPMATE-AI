"""Agent 6 — Recommendation Agent.

Ranks candidate products with the hybrid engine (spec match, budget,
preference similarity, review evidence) and attaches per-product reasons.
"""

import logging
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.product_service import get_products
from app.services.recommendation_service import explain_weights, rank_products

logger = logging.getLogger("shopmate.agents.recommendation")


class RecommendationAgent:
    name = "recommendation"

    async def run(
        self,
        db: Session,
        query: str,
        products: Optional[list[dict[str, Any]]] = None,
        category: Optional[str] = None,
        budget_max: Optional[float] = None,
        budget_min: Optional[float] = None,
        requirements: Optional[dict[str, Any]] = None,
        usage: Optional[list[str]] = None,
        preferences: Optional[dict[str, Any]] = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        started = time.perf_counter()

        # Prefer the discovery branch's products; fall back to category search.
        db_products: list[Product] = []
        if products:
            ids = [p.get("product_id") or p.get("id") for p in products]
            db_products = get_products(db, [i for i in ids if i])

        if not db_products:
            from app.services.product_service import search_products

            response = await search_products(
                db, query=query, category=category,
                budget_min=budget_min, budget_max=budget_max, limit=limit * 2,
            )
            db_products = get_products(db, [p.id for p in response.products])

        ranked = rank_products(
            db,
            products=db_products,
            query=query,
            category=category,
            budget_max=budget_max,
            budget_min=budget_min,
            requirements=requirements or {},
            usage=usage or [],
            preferences=preferences or {},
            limit=limit,
        )

        return {
            "ranked": [r.model_dump(mode="json") for r in ranked],
            "weights": explain_weights(category),
            "took_ms": int((time.perf_counter() - started) * 1000),
        }
