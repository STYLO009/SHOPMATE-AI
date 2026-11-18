"""Recommendation + review analysis endpoints (direct agent access)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.chat_schema import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.product_service import search_products
from app.services.recommendation_service import explain_weights, rank_products

logger = logging.getLogger("shopmate.api.ai")
router = APIRouter(prefix="/api", tags=["ai"])


@router.post("/recommendations", response_model=RecommendationResponse)
async def recommendations(
    payload: RecommendationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hybrid, explainable ranking over fresh provider results."""
    try:
        response = await search_products(
            db,
            query=payload.query,
            category=payload.category,
            budget_max=payload.budget_max,
            limit=max(payload.limit * 3, 15),
        )
        products = response.products
        ranked = rank_products(
            db,
            products=products,
            query=payload.query,
            category=payload.category,
            budget_max=payload.budget_max,
            requirements=payload.preferences.get("requirements") or {},
            usage=payload.usage,
            preferences=payload.preferences,
            limit=payload.limit,
        )
        notes: list[str] = []
        if response.is_sample_data:
            notes.append("Results come from the clearly-labelled sample dataset.")
        if response.provider_errors:
            notes.extend(response.provider_errors)
        if not ranked:
            notes.append("No products matched your requirements.")
        return RecommendationResponse(
            ranked=ranked,
            weights=explain_weights(payload.category),
            llm_mode="rule-based-fallback" if not ranked else "hybrid",
            notes=notes,
        )
    except Exception:
        logger.exception("recommendations_failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "recommendations_failed",
                    "message": "Could not build recommendations."},
        )
