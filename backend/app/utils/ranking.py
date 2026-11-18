"""Explainable hybrid ranking for the recommendation engine.

Final Score = 0.35·spec_match + 0.25·budget_suitability
            + 0.20·preference_similarity + 0.20·review_quality

Weights are configurable globally (Settings) and overridable per category.
Every factor returns both a 0..1 score and a human-readable reason, so the
UI can explain *why* a product ranks where it does.

Missing review data is never treated as a perfect score: it maps to
NEUTRAL_REVIEW_SCORE (below average), and the reason says so explicitly.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import settings
from app.utils.validators import clamp

NEUTRAL_REVIEW_SCORE = 0.4  # "no data" ≠ "perfect"

# Per-category weight overrides (sum to 1.0). Base weights come from Settings.
CATEGORY_WEIGHTS: dict[str, dict[str, float]] = {
    "laptop": {"spec": 0.40, "budget": 0.22, "preference": 0.18, "review": 0.20},
    "smartphone": {"spec": 0.35, "budget": 0.25, "preference": 0.20, "review": 0.20},
    "headphones": {"spec": 0.30, "budget": 0.30, "preference": 0.20, "review": 0.20},
    "smartwatch": {"spec": 0.30, "budget": 0.28, "preference": 0.22, "review": 0.20},
    "default": {},
}

# How strongly each specification key counts for a category (0..1).
SPEC_KEY_WEIGHTS: dict[str, dict[str, float]] = {
    "laptop": {
        "ram_gb": 1.0, "storage_gb": 0.7, "gpu": 0.9, "cpu": 0.9,
        "battery_hours": 0.7, "screen_size_in": 0.4, "refresh_rate_hz": 0.5,
        "weight_kg": 0.3,
    },
    "smartphone": {
        "camera_mp": 0.8, "battery_hours": 0.9, "ram_gb": 0.7, "storage_gb": 0.6,
        "refresh_rate_hz": 0.6, "charging_w": 0.5, "cpu": 0.8, "storage_type": 0.4,
    },
    "headphones": {
        "anc": 0.9, "battery_hours": 1.0, "driver_mm": 0.5, "bluetooth": 0.5,
        "multipoint": 0.5, "water_resistance": 0.4, "type": 0.4,
    },
    "smartwatch": {
        "battery_days": 1.0, "gps": 0.8, "spo2": 0.6, "display": 0.7,
        "water_resistance": 0.6, "screen_size_in": 0.4,
    },
    "default": {},
}


def get_weights(category: Optional[str]) -> dict[str, float]:
    """Base weights (from settings) merged with category overrides."""
    base = {
        "spec": settings.weight_spec,
        "budget": settings.weight_budget,
        "preference": settings.weight_preference,
        "review": settings.weight_review,
    }
    override = CATEGORY_WEIGHTS.get((category or "").lower()) or CATEGORY_WEIGHTS["default"]
    if override:
        base.update(override)
    total = sum(base.values()) or 1.0
    return {k: v / total for k, v in base.items()}  # normalise to sum 1


def spec_key_weights(category: Optional[str]) -> dict[str, float]:
    return SPEC_KEY_WEIGHTS.get((category or "").lower()) or SPEC_KEY_WEIGHTS["default"]


@dataclass
class FactorScores:
    spec_match: float = 0.0
    budget_suitability: float = 0.0
    preference_similarity: float = 0.0
    review_quality: float = NEUTRAL_REVIEW_SCORE
    reasons: list[str] = field(default_factory=list)
    missing_specs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, float]:
        return {
            "spec_match": round(self.spec_match, 4),
            "budget_suitability": round(self.budget_suitability, 4),
            "preference_similarity": round(self.preference_similarity, 4),
            "review_quality": round(self.review_quality, 4),
        }


def score_spec_match(
    requirements: dict[str, Any],
    product_specs: dict[str, Any],
    category: Optional[str],
) -> tuple[float, list[str], list[str]]:
    """0..1 score of how well hard requirements are satisfied.

    `requirements` uses the query-agent schema: {"ram_min": 16, "gpu_required": True, ...}
    """
    if not requirements:
        return 0.6, ["No hard specifications requested — scored on general fit."], []

    checks: list[tuple[bool, str]] = []
    missing: list[str] = []

    # Numeric minimums: ram_min, storage_min, battery_min_hours ...
    numeric_map = {
        "ram_min": ("ram_gb", "RAM ≥ {v}GB"),
        "storage_min": ("storage_gb", "storage ≥ {v}GB"),
        "battery_min_hours": ("battery_hours", "battery ≥ {v}h"),
        "battery_min_days": ("battery_days", "battery ≥ {v} days"),
        "camera_min_mp": ("camera_mp", "camera ≥ {v}MP"),
        "screen_min": ("screen_size_in", "screen ≥ {v}in"),
    }
    for req_key, (spec_key, label) in numeric_map.items():
        if req_key in requirements and requirements[req_key] is not None:
            want = requirements[req_key]
            have = product_specs.get(spec_key)
            if have is None:
                missing.append(spec_key)
            else:
                try:
                    checks.append((float(have) >= float(want), label.format(v=want)))
                except (TypeError, ValueError):
                    missing.append(spec_key)

    if requirements.get("gpu_required") is not None:
        gpu = str(product_specs.get("gpu") or "").lower()
        integrated = any(w in gpu for w in ("integrated", "radeon 7", "intel uhd", "intel arc"))
        has_dedicated = bool(gpu) and not integrated and gpu != "none"
        if requirements["gpu_required"]:
            checks.append((has_dedicated, "dedicated GPU"))
        else:
            checks.append((True, "integrated graphics acceptable"))

    if requirements.get("os"):
        want_os = str(requirements["os"]).lower()
        have_os = str(product_specs.get("os") or "").lower()
        if not have_os:
            missing.append("os")
        else:
            checks.append((want_os in have_os, f"{requirements['os']}"))

    if not checks:
        return (0.6 if not missing else 0.4,
                ["Some requested specs are not published for this product."], missing)

    passed = sum(1 for ok, _ in checks if ok)
    score = passed / len(checks)
    reasons = [
        (f"✔ {label}" if ok else f"✘ Does not meet: {label}")
        for ok, label in checks
    ]
    if missing:
        reasons.append("Not published: " + ", ".join(sorted(set(missing))))
    return score, reasons, missing


def score_budget(price: float, budget_max: Optional[float],
                 budget_min: Optional[float] = None) -> tuple[float, str]:
    """Prefer products that fit the budget with headroom; penalise over-budget."""
    if budget_max is None and budget_min is None:
        return 0.6, "No budget specified — scored on general value."
    if budget_max is None:
        if price >= (budget_min or 0):
            return 0.8, "Meets the minimum budget."
        return 0.3, f"Below the minimum budget of {budget_min:,.0f}."
    if price > budget_max:
        # Over budget: linear penalty — 20% over budget scores ~0.
        over = (price - budget_max) / budget_max
        return clamp(1.0 - over * 5.0, 0.0, 1.0), (
            f"Over budget by ₹{price - budget_max:,.0f}."
        )
    remaining = budget_max - price
    # Full marks at ≥20% headroom, 0.75 when just under the cap.
    headroom = remaining / budget_max
    score = clamp(0.75 + headroom * 1.25, 0.0, 1.0)
    return score, f"Fits the budget (₹{remaining:,.0f} headroom)."


def score_review(
    rating: Optional[float],
    review_count: Optional[int],
) -> tuple[float, str]:
    """0..1 review quality. Missing data → NEUTRAL_REVIEW_SCORE, never 1.0."""
    if rating is None or not review_count:
        return (
            NEUTRAL_REVIEW_SCORE,
            "No review data available for this product (not counted as a positive signal).",
        )
    # Scale 3.0..5.0 stars onto 0..1 (below 3.0 scores 0).
    star_score = clamp((float(rating) - 3.0) / 2.0, 0.0, 1.0)
    # Confidence: few reviews → pull toward the neutral prior.
    confidence = clamp(review_count / 50.0, 0.0, 1.0)
    score = NEUTRAL_REVIEW_SCORE + (star_score - NEUTRAL_REVIEW_SCORE) * confidence
    return (
        clamp(score, 0.0, 1.0),
        f"Rated {rating:.1f}★ from {review_count} review{'s' if review_count != 1 else ''}.",
    )


def weighted_final(factors: FactorScores, category: Optional[str]) -> float:
    w = get_weights(category)
    return round(
        w["spec"] * factors.spec_match
        + w["budget"] * factors.budget_suitability
        + w["preference"] * factors.preference_similarity
        + w["review"] * factors.review_quality,
        4,
    )
