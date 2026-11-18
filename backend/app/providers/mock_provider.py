"""Sample-data provider adapter.

Searches the clearly-labelled sample dataset with deterministic matching
(keyword + category + budget filters). Used for local development, tests and
as an explicit fallback when no merchant API credentials are configured.
"""

import re
import time
from typing import Any, Optional

from app.providers.art import product_art_url
from app.providers.base import ProductProvider, ProviderProduct
from app.providers.sample_data import SAMPLE_PRODUCTS
from app.core.config import settings

CATEGORY_KEYWORDS = {
    "laptop": ["laptop", "notebook", "ultrabook"],
    "smartphone": ["phone", "iphone", "galaxy", "smartphone", "mobile"],
    "headphones": ["headphone", "earbud", "earbuds", "headset", "anc"],
    "smartwatch": ["watch", "smartwatch", "fitness band"],
    "tablet": ["tablet", "pad"],
    "camera": ["camera", "mirrorless", "lens"],
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "under", "over", "best",
    "buy", "find", "show", "me", "please", "i", "need", "want", "to", "of",
    "in", "on", "is", "that", "this", "it", "my", "me", "get", "new",
}


def _detect_category(query: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit.lower().strip()
    q = query.lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        # Word-boundary match so "headphones" doesn't match "phone".
        if any(re.search(rf"\b{re.escape(w)}s?\b", q) for w in words):
            return cat
    return None


def _keywords(query: str) -> list[str]:
    tokens = [
        t for t in "".join(ch.lower() if ch.isalnum() else " " for ch in query).split()
        if len(t) > 1 and t not in STOPWORDS
    ]
    return tokens


def _score(product: dict[str, Any], keywords: list[str], category: Optional[str]) -> int:
    text = " ".join(
        [product.get("title", ""), product.get("brand", "") or "",
         product.get("description", "") or "",
         product.get("category", "") or ""]
    ).lower()
    score = 0
    for kw in keywords:
        if kw in text:
            score += 3
            if kw in product.get("title", "").lower():
                score += 2
    if category and product.get("category") == category:
        score += 5
    return score


class SampleDataProvider(ProductProvider):
    """Clearly-labelled sample dataset provider."""

    name = "sample_dataset"
    source_type = "sample"

    def __init__(self) -> None:
        self._art_key = {p["id"]: p.get("category", "default") for p in SAMPLE_PRODUCTS}

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        limit: int = 20,
    ) -> list[ProviderProduct]:
        started = time.perf_counter()
        cat = _detect_category(query, category)
        keywords = _keywords(query)

        candidates = []
        for p in SAMPLE_PRODUCTS:
            if cat and p.get("category") != cat:
                continue
            if budget_max is not None and p["price"] > budget_max:
                continue
            if budget_min is not None and p["price"] < budget_min:
                continue
            s = _score(p, keywords, cat)
            if keywords and s == 0 and not cat:
                continue  # no textual or categorical match at all
            candidates.append((s, p))

        # Deterministic ordering: match score desc, then price asc, then id.
        candidates.sort(key=lambda t: (-t[0], t[1]["price"], t[1]["id"]))
        selected = [p for _, p in candidates[:limit]]

        elapsed = int((time.perf_counter() - started) * 1000)
        _ = elapsed  # timing available for logging if needed

        return [self._to_product(p) for p in selected]

    async def get_product(self, provider_product_id: str) -> Optional[ProviderProduct]:
        for p in SAMPLE_PRODUCTS:
            if p["id"] == provider_product_id:
                return self._to_product(p)
        return None

    def _to_product(self, p: dict[str, Any]) -> ProviderProduct:
        category = p.get("category") or "default"
        art_key = category if category in ("laptop", "smartphone", "headphones",
                                           "smartwatch", "tablet", "camera") else "default"
        return ProviderProduct(
            provider_product_id=p["id"],
            title=p["title"],
            price=float(p["price"]),
            merchant=p.get("merchant", "SampleStore"),
            currency=p.get("currency", "INR"),
            brand=p.get("brand"),
            category=p.get("category"),
            description=p.get("description"),
            product_url=p.get("product_url"),
            image_url=product_art_url(settings.backend_url, art_key),
            specifications=dict(p.get("specifications") or {}),
            rating=p.get("rating"),
            review_count=p.get("review_count"),
            availability=p.get("availability", "unknown"),
            source_type="sample",
            source_name="Sample dataset (demo)",
            is_sample_data=True,
            reviews=list(p.get("reviews") or []),
        )
