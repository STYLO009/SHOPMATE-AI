"""Product service: provider orchestration, persistence, search & compare."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import PriceHistory, Product, ProductReview
from app.providers import ProviderRegistry, get_registry
from app.providers.base import ProviderProduct
from app.schemas.product_schema import (
    ComparisonResult,
    ProductOut,
    SearchResponse,
    SpecDifference,
)
from app.utils.validators import normalize_text

logger = logging.getLogger("shopmate.products")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def upsert_product(db: Session, record: ProviderProduct) -> Product:
    """Persist a provider record (idempotent on provider+external id)."""
    product = db.scalar(
        select(Product).where(
            Product.provider_product_id == record.provider_product_id,
            Product.source_name == record.source_name,
        )
    )
    if product is None:
        # Also match by provider id alone when the source name changed.
        product = db.scalar(
            select(Product).where(
                Product.provider_product_id == record.provider_product_id
            )
        )

    fields: dict[str, Any] = {
        "title": record.title,
        "brand": record.brand,
        "category": record.category,
        "description": record.description,
        "price": record.price,
        "currency": record.currency,
        "merchant": record.merchant,
        "product_url": record.product_url,
        "image_url": record.image_url,
        "specifications": record.specifications,
        "rating": record.rating,
        "review_count": record.review_count,
        "availability": record.availability,
        "source_type": record.source_type,
        "source_name": record.source_name,
        "is_sample_data": record.is_sample_data,
        "last_verified_at": record.last_verified_at,
    }

    if product is None:
        product = Product(provider_product_id=record.provider_product_id, **fields)
        db.add(product)
        db.flush()
    else:
        price_changed = abs(product.price - record.price) > 1e-9
        for k, v in fields.items():
            setattr(product, k, v)
        if price_changed:
            db.add(
                PriceHistory(
                    product_id=product.id,
                    merchant=record.merchant,
                    price=record.price,
                    currency=record.currency,
                    availability=record.availability,
                )
            )
        db.flush()

    # Store provider-supplied reviews verbatim (never generated).
    for rev in record.reviews:
        body = (rev.get("body") or "").strip()
        if not body:
            continue
        exists = db.scalar(
            select(ProductReview).where(
                ProductReview.product_id == product.id,
                ProductReview.body == body,
            )
        )
        if exists is None:
            db.add(
                ProductReview(
                    product_id=product.id,
                    reviewer_name=rev.get("reviewer_name"),
                    rating=rev.get("rating"),
                    title=rev.get("title"),
                    body=body,
                    source=rev.get("source", record.source_name),
                )
            )
    db.flush()
    return product


def _sort_products(products: list[Product], sort_by: str) -> list[Product]:
    if sort_by == "price_asc":
        return sorted(products, key=lambda p: p.price)
    if sort_by == "price_desc":
        return sorted(products, key=lambda p: -p.price)
    if sort_by == "rating":
        return sorted(products, key=lambda p: (p.rating or 0, p.review_count or 0), reverse=True)
    return products  # relevance (provider order)


async def search_products(
    db: Session,
    query: str,
    category: Optional[str] = None,
    budget_min: Optional[float] = None,
    budget_max: Optional[float] = None,
    limit: int = 12,
    sort_by: str = "relevance",
    registry: Optional[ProviderRegistry] = None,
) -> SearchResponse:
    """Query providers, persist results, and return a normalised response."""
    started = time.perf_counter()
    registry = registry or get_registry()

    result = await registry.search(
        query=query, category=category,
        budget_min=budget_min, budget_max=budget_max, limit=max(limit * 2, 20),
    )

    products = [upsert_product(db, p) for p in result.products]
    db.commit()

    products = _sort_products(products, sort_by)
    total = len(products)
    page = products[:limit]

    return SearchResponse(
        products=[ProductOut.model_validate(p) for p in page],
        total=total,
        query=query,
        category=category,
        providers_queried=registry.provider_names,
        provider_errors=[result.error] if result.error else [],
        is_sample_data=result.is_sample_data,
        took_ms=int((time.perf_counter() - started) * 1000),
    )


async def featured_products(
    db: Session,
    limit: int = 24,
    category: Optional[str] = None,
    registry: Optional[ProviderRegistry] = None,
) -> SearchResponse:
    """Catalogue feed for the Explore landing state (no query required).

    Mirrors `search_products` but starts from an empty query so the sample
    dataset (or any configured live provider that accepts it) fills the grid
    the moment the page opens — the way a storefront homepage behaves.
    """
    started = time.perf_counter()
    registry = registry or get_registry()

    result = await registry.search(
        query="", category=category, limit=max(limit * 2, 20),
    )

    products = [upsert_product(db, p) for p in result.products]
    db.commit()

    # Featured ordering: best rated first, then most reviewed, then cheapest.
    products.sort(
        key=lambda p: (-(p.rating or 0.0), -(p.review_count or 0), p.price),
    )
    total = len(products)
    page = products[:limit]

    # "not_configured" is expected state, not a problem worth alarming the UI.
    errors: list[str] = []
    for chunk in (result.error or "").split("; "):
        if chunk and "not_configured" not in chunk:
            errors.append(chunk)

    return SearchResponse(
        products=[ProductOut.model_validate(p) for p in page],
        total=total,
        query="",
        category=category,
        providers_queried=registry.provider_names,
        provider_errors=errors,
        is_sample_data=result.is_sample_data,
        took_ms=int((time.perf_counter() - started) * 1000),
    )


def get_product(db: Session, product_id: str) -> Optional[Product]:
    """Fetch by internal id or by provider product id (e.g. 'SMP-LAP-001')."""
    product = db.get(Product, product_id)
    if product is not None:
        return product
    return db.scalar(select(Product).where(Product.provider_product_id == product_id))


def get_products(db: Session, product_ids: list[str]) -> list[Product]:
    out: list[Product] = []
    seen: set[str] = set()
    for pid in product_ids:
        p = get_product(db, pid)
        if p is not None and p.id not in seen:
            seen.add(p.id)
            out.append(p)
    return out


async def resolve_product(
    db: Session, product_id: str, registry: Optional[ProviderRegistry] = None,
) -> Optional[Product]:
    """DB lookup first, then provider fetch + persist.

    Keeps endpoints usable for known provider ids (e.g. 'SMP-PHN-001') even
    before any search has written them to the database.
    """
    product = get_product(db, product_id)
    if product is not None:
        return product
    registry = registry or get_registry()
    record = await registry.get_product(product_id)
    if record is None:
        return None
    product = upsert_product(db, record)
    db.commit()
    return product


def _name_match_score(query_low: str, title: str, brand: Optional[str]) -> int:
    """Score how specifically a product name is referenced in the query.

    10 = full product name appears (e.g. "iphone 15" in the query);
     6 = every distinctive token appears (model + brand tokens);
     0 = not referenced.
    """
    import re as _re

    base = _re.sub(r"\([^)]*\)", "", title or "").strip()
    base = normalize_text(base)
    if not base:
        return 0
    brand_low = normalize_text(brand or "")
    variants = [base]
    if brand_low and base.startswith(brand_low + " "):
        variants.append(base[len(brand_low) + 1:])

    score = 0
    for v in variants:
        if v and v in query_low:
            score = max(score, 10)
            break

    if score == 0:
        generic = {"the", "and", "with", "for", "new", "plus", "edition", "gb",
                   "tb", "inch", "in", "smartphone", "laptop", "headphones"}
        tokens = [t for t in variants[-1].split() if t not in generic and len(t) >= 2]
        if tokens and all(
            _re.search(rf"\b{_re.escape(t)}\b", query_low) for t in tokens
        ):
            score = 6
    return score


async def resolve_targets_from_text(
    db: Session, text: str, registry: Optional[ProviderRegistry] = None,
    limit: int = 4,
) -> list[str]:
    """Resolve product references in free text to internal product ids.

    Handles explicit ids (SMP-XXX-NNN / UUIDs) and product names
    ("iPhone 15", "Samsung Galaxy S24"). Matched provider records are
    persisted so downstream agents can read their real reviews/specs.
    """
    import re

    registry = registry or get_registry()
    resolved: list[str] = []
    query_low = normalize_text(text)

    # 1) explicit ids in the text
    explicit = re.findall(r"\bSMP-[A-Z]{3}-\d{3}\b", text)
    explicit += re.findall(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", text
    )
    for pid in explicit:
        p = get_product(db, pid)
        if p is None:
            # May be a provider id not yet persisted — fetch + persist it.
            record = await registry.get_product(pid)
            if record is not None:
                p = upsert_product(db, record)
                db.commit()
        if p is not None and p.id not in resolved:
            resolved.append(p.id)
    if resolved:
        return resolved

    # 2) product-name matching against persisted products
    candidates = db.scalars(select(Product).limit(500)).all()
    scored: list[tuple[int, Product]] = []
    for p in candidates:
        s = _name_match_score(query_low, p.title, p.brand)
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda t: (-t[0], t[1].price))
    for _, p in scored[:limit]:
        if p.id not in resolved:
            resolved.append(p.id)
    if resolved:
        return resolved

    # 3) last resort: match against the provider catalogue (sample dataset etc.)
    try:
        results = await registry.search(query=text, limit=limit * 3)
    except Exception:
        return []
    scored2: list[tuple[int, Any]] = []
    for record in results.products:
        s = _name_match_score(query_low, record.title, record.brand)
        if s > 0:
            scored2.append((s, record))
    scored2.sort(key=lambda t: -t[0])
    if not scored2:
        # No direct name match: fall back to the provider's keyword search so
        # "compare iPhone and Samsung phones" still resolves sensible targets.
        scored2 = [(1, r) for r in results.products[:limit]]
    for _, record in scored2[:limit]:
        p = upsert_product(db, record)
        if p.id not in resolved:
            resolved.append(p.id)
    db.commit()
    return resolved


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

_NUMERIC_SPEC_DIRECTIONS: dict[str, str] = {
    # "higher_is_better" | "lower_is_better"
    "ram_gb": "higher_is_better",
    "storage_gb": "higher_is_better",
    "refresh_rate_hz": "higher_is_better",
    "battery_hours": "higher_is_better",
    "battery_days": "higher_is_better",
    "camera_mp": "higher_is_better",
    "megapixels": "higher_is_better",
    "charging_w": "higher_is_better",
    "driver_mm": "neutral",
    "screen_size_in": "neutral",
    "weight_kg": "lower_is_better",
    "cpu": "neutral",
    "gpu": "neutral",
    "anc": "presence",
    "gps": "presence",
    "spo2": "presence",
    "multipoint": "presence",
    "5g": "presence",
    "water_resistance": "presence",
}


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def compare_products(db: Session, product_ids: list[str]) -> ComparisonResult:
    """Build a side-by-side comparison with meaningful difference detection."""
    products = get_products(db, product_ids)
    if len(products) < 2:
        raise ValueError("At least two valid products are required for comparison.")

    prices = [p.price for p in products]
    cheapest = min(products, key=lambda p: p.price)

    # Union of specification keys across products.
    all_keys: list[str] = []
    for p in products:
        for k in p.specifications.keys():
            if k not in all_keys:
                all_keys.append(k)

    differences: list[SpecDifference] = []
    missing: list[str] = []
    for key in all_keys:
        values = {p.id: p.specifications.get(key) for p in products}
        published = {pid: v for pid, v in values.items() if v is not None}
        if len(published) < len(products):
            missing.append(key)

        fmt_values = {pid: _fmt(v) for pid, v in values.items()}
        direction = _NUMERIC_SPEC_DIRECTIONS.get(key, "neutral")
        better_id: Optional[str] = None
        explanation: Optional[str] = None

        if direction in ("higher_is_better", "lower_is_better") and len(published) >= 2:
            numeric = {}
            for pid, v in published.items():
                try:
                    numeric[pid] = float(v)
                except (TypeError, ValueError):
                    numeric = {}
                    break
            if numeric:
                better_id = (
                    max(numeric, key=numeric.get)  # type: ignore[arg-type]
                    if direction == "higher_is_better"
                    else min(numeric, key=numeric.get)  # type: ignore[arg-type]
                )
                vals = list(numeric.values())
                if max(vals) != min(vals):
                    explanation = (
                        f"{key.replace('_', ' ')} differs by "
                        f"{abs(max(vals) - min(vals)):g} "
                        f"({'higher' if direction == 'higher_is_better' else 'lower'} is better)."
                    )
        elif direction == "presence":
            yes = [pid for pid, v in published.items() if v is True]
            no = [pid for pid, v in published.items() if v is False]
            if yes and no:
                better_id = yes[0]
                explanation = f"Only some products have {key.replace('_', ' ')}."

        # Only report rows where products actually differ.
        if len(set(fmt_values.values())) > 1:
            differences.append(
                SpecDifference(spec=key, values=fmt_values, better=better_id,
                               explanation=explanation)
            )

    price_difference = round(max(prices) - min(prices), 2) if len(prices) > 1 else None

    # Staleness: anything not verified in the last 24h is flagged as stale.
    now = utcnow()
    stale = [
        p.id for p in products
        if p.last_verified_at and (now - p.last_verified_at.replace(tzinfo=timezone.utc)
                                   if p.last_verified_at.tzinfo is None
                                   else now - p.last_verified_at).total_seconds() > 86400
    ]

    best_value = _pick_best_value(products, differences)
    verdict = _build_verdict(products, cheapest, best_value, price_difference)

    return ComparisonResult(
        products=[ProductOut.model_validate(p) for p in products],
        price_difference=price_difference,
        cheapest_product_id=cheapest.id,
        spec_differences=differences,
        missing_specs=missing,
        stale_products=stale,
        verdict=verdict,
        best_value_id=best_value,
    )


def _build_verdict(
    products: list[Product],
    cheapest: Product,
    best_value_id: Optional[str],
    price_difference: Optional[float],
) -> str:
    """One honest sentence derived only from computed comparison facts."""
    by_id = {p.id: p for p in products}
    value = by_id.get(best_value_id or "")
    price_bit = (
        f" Prices differ by {price_difference:,.0f}."
        if price_difference and price_difference > 0
        else " Both are priced the same."
    )
    if value is None or value.id == cheapest.id:
        return (
            f"{cheapest.title} is the cheapest at "
            f"{cheapest.price:,.0f} {cheapest.currency} and wins on specification "
            f"value.{price_bit}"
        )
    return (
        f"{cheapest.title} is cheapest at {cheapest.price:,.0f} {cheapest.currency}, "
        f"while {value.title} offers better specification value at "
        f"{value.price:,.0f} {value.currency}.{price_bit}"
    )


def _pick_best_value(products: list[Product], differences: list[SpecDifference]) -> Optional[str]:
    """Cheap value heuristic: count spec wins per product, break ties on price."""
    wins: dict[str, int] = {p.id: 0 for p in products}
    for d in differences:
        if d.better and d.better in wins:
            wins[d.better] += 1
    if not any(wins.values()):
        return min(products, key=lambda p: p.price).id
    # Prefer most spec wins, then lowest price among leaders.
    top = max(wins.values())
    leaders = [p for p in products if wins[p.id] == top]
    return min(leaders, key=lambda p: p.price).id


def product_to_card(p: Product, reason: Optional[str] = None,
                    score: Optional[float] = None) -> dict[str, Any]:
    """Shared dict shape used by product cards in chat / compare / lists."""
    return {
        "product_id": p.id,
        "title": p.title,
        "brand": p.brand,
        "merchant": p.merchant,
        "price": p.price,
        "currency": p.currency,
        "image_url": p.image_url,
        "rating": p.rating,
        "review_count": p.review_count,
        "source_type": p.source_type,
        "is_sample_data": p.is_sample_data,
        "product_url": p.product_url,
        "reason": reason,
        "score": score,
    }
