"""Product endpoints: search, detail, compare, suggestions."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.product_schema import (
    CompareRequest,
    ComparisonResult,
    ProductOut,
    SearchRequest,
    SearchResponse,
)
from app.services import product_service

logger = logging.getLogger("shopmate.api.products")
router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, db: Session = Depends(get_db)):
    """Search products across all configured providers (normalised)."""
    if request.budget_min is not None and request.budget_max is not None:
        if request.budget_min > request.budget_max:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_budget",
                        "message": "budget_min must be <= budget_max."},
            )
    try:
        return await product_service.search_products(
            db,
            query=request.query,
            category=request.category,
            budget_min=request.budget_min,
            budget_max=request.budget_max,
            limit=request.limit,
            sort_by=request.sort_by,
        )
    except Exception:
        logger.exception("product_search_failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "search_failed",
                    "message": "Product search failed. Please try again."},
        )


@router.get("/featured", response_model=SearchResponse)
async def featured(category: Optional[str] = None,
                   limit: int = Query(default=24, ge=1, le=50),
                   db: Session = Depends(get_db)):
    """Catalogue feed for the Explore landing state — no query required.

    Registered before `/{product_id}` so "featured" is never treated as a id.
    """
    try:
        return await product_service.featured_products(
            db, limit=limit, category=category,
        )
    except Exception:
        logger.exception("featured_feed_failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "featured_failed",
                    "message": "Could not load the catalogue feed."},
        )


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: Session = Depends(get_db)):
    """Fetch one product by internal id or provider id (e.g. SMP-LAP-001)."""
    product = await product_service.resolve_product(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "product_not_found",
                    "message": "No product matches that id."},
        )
    return ProductOut.model_validate(product)


@router.post("/compare", response_model=ComparisonResult)
async def compare(request: CompareRequest, db: Session = Depends(get_db)):
    """Side-by-side comparison with difference detection and a verdict."""
    if len(set(request.product_ids)) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "need_two_products",
                    "message": "Provide at least two distinct product ids."},
        )
    try:
        # Fetch unknown ids from providers so compare works pre-search.
        for pid in request.product_ids:
            await product_service.resolve_product(db, pid)
        return product_service.compare_products(db, request.product_ids)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "products_not_found", "message": str(exc)},
        )
    except Exception:
        logger.exception("compare_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "compare_failed", "message": "Comparison failed."},
        )


@router.get("/list/suggestions")
def suggestions(db: Session = Depends(get_db),
                limit: int = Query(default=8, ge=1, le=30)):
    """Popular sample categories/prompts for the dashboard (derived from DB)."""
    from sqlalchemy import func, select

    from app.models.product import Product

    rows = db.execute(
        select(Product.category, func.count(Product.id), func.max(Product.is_sample_data))
        .group_by(Product.category)
        .order_by(func.count(Product.id).desc())
        .limit(limit)
    ).all()
    return {
        "categories": [{"category": c, "count": n} for c, n, _ in rows if c],
        "is_sample_data": bool(rows) and all(is_sample for _, _, is_sample in rows),
    }
