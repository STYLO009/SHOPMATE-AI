"""Review endpoints (thin wrapper over the review analysis service)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.chat_schema import ReviewAnalyzeRequest, ReviewAnalysisResponse
from app.services.product_service import get_product
from app.services.review_service import analyze_product_reviews

logger = logging.getLogger("shopmate.api.reviews")
router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/analyze", response_model=ReviewAnalysisResponse)
async def analyze(
    payload: ReviewAnalyzeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyse ACTUAL stored reviews for a product (never invented)."""
    product = None
    if payload.product_id:
        from app.services.product_service import resolve_product

        product = await resolve_product(db, payload.product_id)
    elif payload.query:
        from app.services.product_service import search_products

        response = await search_products(db, query=payload.query, limit=1)
        if response.products:
            product = get_product(db, response.products[0].id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "product_not_found",
                    "message": "No product found to analyse reviews for."},
        )
    try:
        return await analyze_product_reviews(db, product)
    except Exception:
        logger.exception("review_analysis_failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "review_analysis_failed",
                    "message": "Review analysis failed."},
        )
