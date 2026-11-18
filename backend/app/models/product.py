"""Product, price-history and user preference models.

Product rows are written by provider adapters (normalised copies of external
records) so that search/recommendation never depend on a specific merchant.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Product(Base):
    """Normalised product record (see schemas/product_schema.py)."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Stable provider-scoped identifier (e.g. "sample:B08XYZ")
    provider_product_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    merchant: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    product_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    specifications: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    availability: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    # "sample" | "merchant_api" | "affiliate_feed" | "user_url" | "public_dataset"
    source_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(128), default="unknown", nullable=False)
    is_sample_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    price_history = relationship("PriceHistory", back_populates="product",
                                 cascade="all, delete-orphan")
    reviews = relationship("ProductReview", back_populates="product",
                           cascade="all, delete-orphan")


class PriceHistory(Base):
    """Append-only merchant price snapshots for watchlist / freshness checks."""

    __tablename__ = "price_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    merchant: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    availability: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    product = relationship("Product", back_populates="price_history")


class ProductReview(Base):
    """Actual reviews supplied by a data provider (never generated)."""

    __tablename__ = "product_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reviewer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(128), default="sample_dataset", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product = relationship("Product", back_populates="reviews")


class UserPreference(Base):
    """Persistent shopping preferences used by the recommendation engine."""

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    favorite_categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    preferred_brands: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    budget_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    usage: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    priorities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="preferences")
