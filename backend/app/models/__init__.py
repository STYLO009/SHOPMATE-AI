"""ORM model registry — import this to register every table."""

from app.models.conversation import (  # noqa: F401
    Conversation,
    Message,
    SavedProduct,
    WatchlistEntry,
)
from app.models.product import PriceHistory, Product, ProductReview, UserPreference  # noqa: F401
from app.models.user import PasswordResetToken, User  # noqa: F401

__all__ = [
    "User",
    "PasswordResetToken",
    "UserPreference",
    "Product",
    "PriceHistory",
    "ProductReview",
    "Conversation",
    "Message",
    "SavedProduct",
    "WatchlistEntry",
]
