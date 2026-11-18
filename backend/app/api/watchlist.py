"""Saved products + price watchlist endpoints (user-scoped)."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.comparison_schema import (
    SavedProductOut,
    WatchlistCreateRequest,
    WatchlistEntryOut,
)
from app.services import conversation_service, pricing_service
from app.services.product_service import product_to_card

logger = logging.getLogger("shopmate.api.watchlist")
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _saved_out(entry) -> SavedProductOut:
    return SavedProductOut(
        id=entry.id,
        product=product_to_card(entry.product),
        note=entry.note,
        created_at=entry.created_at,
    )


def _watch_out(entry) -> WatchlistEntryOut:
    return WatchlistEntryOut(
        id=entry.id,
        product=product_to_card(entry.product),
        target_price=entry.target_price,
        last_price=entry.last_price,
        last_checked_at=entry.last_checked_at,
        check_count=entry.check_count,
        created_at=entry.created_at,
    )


# --- saved products --------------------------------------------------------

@router.post("/saved", response_model=SavedProductOut, status_code=status.HTTP_201_CREATED)
def save_product(payload: WatchlistCreateRequest,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    entry = conversation_service.save_product(db, user.id, payload.product_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "product_not_found", "message": "Product not found."},
        )
    db.refresh(entry)
    return _saved_out(entry)


@router.get("/saved", response_model=list[SavedProductOut])
def list_saved(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return [_saved_out(e) for e in conversation_service.list_saved(db, user.id)]


@router.delete("/saved/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsave(product_id: str, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    if not conversation_service.unsave_product(db, user.id, product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_saved", "message": "Product is not saved."},
        )


# --- price watchlist --------------------------------------------------------

@router.post("", response_model=WatchlistEntryOut, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(payload: WatchlistCreateRequest,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    entry = conversation_service.add_watchlist(
        db, user.id, payload.product_id, payload.target_price
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "product_not_found", "message": "Product not found."},
        )
    return _watch_out(entry)


@router.get("", response_model=list[WatchlistEntryOut])
def list_watchlist(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return [_watch_out(e) for e in conversation_service.list_watchlist(db, user.id)]


@router.post("/refresh")
async def refresh_prices(user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """Re-check watchlist prices with the owning provider (real checks only)."""
    results = await pricing_service.refresh_watchlist_prices(db, user.id)
    return {"results": results, "checked": len(results)}


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_watchlist(product_id: str,
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if not conversation_service.remove_watchlist(db, user.id, product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_watching",
                    "message": "Product is not on your watchlist."},
        )
