"""Hybrid recommendation engine.

Combines four explainable factors (see utils/ranking.py):
    spec_match · budget_suitability · preference_similarity · review_quality

Preference similarity uses real embeddings (Sentence-Transformers when
installed, deterministic TF-IDF fallback otherwise) of the user query +
usage/preferences against product text.
"""

import logging
from typing import Any, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.chat_schema import ProductCard, RankedProduct
from app.services.product_service import product_to_card
from app.utils import embeddings as emb
from app.utils.ranking import (
    FactorScores,
    get_weights,
    score_budget,
    score_review,
    score_spec_match,
    spec_key_weights,
    weighted_final,
)

logger = logging.getLogger("shopmate.recommendations")


def _product_text(p: Product) -> str:
    specs = " ".join(f"{k} {v}" for k, v in (p.specifications or {}).items())
    return " ".join(filter(None, [p.title, p.brand or "", p.category or "",
                                  p.description or "", specs]))


def _preference_scores(
    query: str,
    usage: list[str],
    preferences: dict[str, Any],
    products: list[Product],
) -> np.ndarray:
    """Cosine similarity between the research intent and each product."""
    intent_bits = [query] + list(usage or [])
    for key in ("brand", "preferred_brands", "priorities", "requirements"):
        v = preferences.get(key)
        if isinstance(v, str):
            intent_bits.append(v)
        elif isinstance(v, list):
            intent_bits.extend(str(x) for x in v)
    intent = " ".join(filter(None, intent_bits))

    corpus = [_product_text(p) for p in products]
    vectors = emb.embed([intent] + corpus, corpus=corpus)
    sims = emb.cosine_matrix(vectors[0:1], vectors[1:])[0]
    # Shift from [-1,1] to [0,1] so an unrelated product scores ~0.5 max.
    return np.clip((np.asarray(sims, dtype=np.float32) + 1.0) / 2.0, 0.0, 1.0)


def rank_products(
    db: Session,
    products: list[Product],
    query: str,
    category: Optional[str] = None,
    budget_max: Optional[float] = None,
    budget_min: Optional[float] = None,
    requirements: Optional[dict[str, Any]] = None,
    usage: Optional[list[str]] = None,
    preferences: Optional[dict[str, Any]] = None,
    limit: int = 5,
) -> list[RankedProduct]:
    """Rank products with per-factor scores and human-readable reasons."""
    if not products:
        return []

    requirements = requirements or {}
    usage = usage or []
    preferences = preferences or {}
    cat = category or products[0].category

    # Preference similarity (semantic) for all products in one embedding pass.
    pref_scores = _preference_scores(query, usage, preferences, products)
    spec_w = spec_key_weights(cat)

    ranked: list[RankedProduct] = []
    for i, p in enumerate(products):
        factors = FactorScores()

        factors.spec_match, spec_reasons, missing = score_spec_match(
            requirements, p.specifications or {}, cat
        )
        # Missing specs the user asked for already reduce spec_match inside
        # score_spec_match; record them for the UI.
        factors.missing_specs = missing

        factors.budget_suitability, budget_reason = score_budget(
            p.price, budget_max, budget_min
        )
        factors.review_quality, review_reason = score_review(p.rating, p.review_count)
        factors.preference_similarity = float(pref_scores[i])

        pref_reason = (
            f"Matches your research intent ({factors.preference_similarity:.0%} "
            f"semantic similarity)."
            if factors.preference_similarity >= 0.55
            else "Only loosely related to your stated requirements."
        )

        final = weighted_final(factors, cat)

        # Reasons: only meaningful signals, capped for readability.
        reasons = [budget_reason, review_reason, pref_reason]
        reasons.extend(r for r in spec_reasons if r.startswith("✘") or r.startswith("✔"))
        if factors.missing_specs:
            reasons.append("Specs not published: " + ", ".join(factors.missing_specs[:4]))
        if p.is_sample_data:
            reasons.append("Sample data (demo dataset, not a live listing).")

        card = ProductCard(**product_to_card(
            p, reason=reasons[0] if reasons else None, score=final
        ))
        ranked.append(RankedProduct(
            product=card,
            final_score=final,
            factor_scores=factors.as_dict(),
            reasons=reasons[:8],
        ))

    ranked.sort(key=lambda r: (-r.final_score, r.product.price))
    return ranked[:limit]


def explain_weights(category: Optional[str]) -> dict[str, float]:
    return {k: round(v, 4) for k, v in get_weights(category).items()}
