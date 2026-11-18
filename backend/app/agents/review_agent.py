"""Agent 4 — Review Analysis Agent.

Delegates to review_service, which only ever analyses reviews actually
supplied by data providers (LLM-assisted or deterministic fallback).
"""

import logging
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.product_service import get_product
from app.services.review_service import analyze_product_reviews

logger = logging.getLogger("shopmate.agents.review")


class ReviewAnalysisAgent:
    name = "review_analysis"

    async def run(
        self,
        db: Session,
        product_ids: Optional[list[str]] = None,
        products_hint: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        ids = list(product_ids or [])
        if not ids and products_hint:
            ids = [p.get("product_id") or p.get("id") for p in products_hint[:1]]
        ids = [i for i in ids if i]

        if not ids:
            return {
                "review_analysis": None,
                "errors": ["No specific product identified for review analysis."],
                "took_ms": 0,
            }

        analyses = []
        errors: list[str] = []
        for pid in ids:
            product = get_product(db, pid)
            if product is None:
                errors.append(f"Product {pid} not found.")
                continue
            analysis = await analyze_product_reviews(db, product)
            analyses.append(analysis.model_dump(mode="json"))

        if not analyses:
            errors.append("No reviews could be analysed.")
            return {"review_analysis": None, "errors": errors, "took_ms": 0}

        return {
            # Single product → flat object; multiple → {"items": [...]}
            "review_analysis": analyses[0] if len(analyses) == 1 else {"items": analyses},
            "errors": errors,
            "took_ms": int((time.perf_counter() - started) * 1000),
        }
