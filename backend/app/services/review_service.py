"""Review analysis over ACTUAL provider-supplied reviews.

Two modes:
- LLM mode: ask the configured model to group real review text into themes.
- Fallback mode: deterministic lexicon-based theme extraction + sentiment.

In both modes only quotes and counts derived from stored reviews are used.
When a product has no reviews the response says so explicitly — sentiment
statistics are never invented.
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product, ProductReview
from app.schemas.chat_schema import ReviewAnalysisResponse, ReviewTheme
from app.services.llm_service import structured_completion
from pydantic import BaseModel, Field

logger = logging.getLogger("shopmate.reviews")


class LLMThemeOutput(BaseModel):
    positive_themes: list[dict[str, Any]] = Field(default_factory=list)
    negative_themes: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    reliability_concerns: list[str] = Field(default_factory=list)


# --- deterministic fallback -------------------------------------------------

POS_WORDS = {
    "excellent", "great", "good", "love", "loved", "best", "amazing", "awesome",
    "solid", "fast", "reliable", "comfortable", "crisp", "sharp", "sturdy",
    "premium", "bright", "smooth", "accurate", "fantastic", "perfect", "clear",
    "powerful", "quiet", "light", "easy", "worth", "recommend", "happy",
    "stunning", "gorgeous", "premium", "insane", "beast", "king",
}
NEG_WORDS = {
    "bad", "poor", "weak", "slow", "loud", "noisy", "cheap", "broken", "issue",
    "issues", "problem", "problems", "disappointing", "average", "bulky",
    "heavy", "cramped", "finicky", "dated", "lacking", "wish", "hot", "warm",
    "drains", "frustrating", "annoying", "fault", "defect", "return",
}

# Domain themes: keyword → theme label (category-agnostic).
THEME_LEXICON = {
    "battery": "Battery life", "charge": "Battery life", "mah": "Battery life",
    "screen": "Display quality", "display": "Display quality",
    "bright": "Display quality", "oled": "Display quality", "amoled": "Display quality",
    "camera": "Camera quality", "photo": "Camera quality", "photos": "Camera quality",
    "video": "Camera quality",
    "performance": "Performance & speed", "fast": "Performance & speed",
    "slow": "Performance & speed", "stutter": "Performance & speed",
    "lag": "Performance & speed", "compiles": "Performance & speed",
    "fan": "Thermals & noise", "fans": "Thermals & noise", "cool": "Thermals & noise",
    "cooling": "Thermals & noise", "heat": "Thermals & noise",
    "warm": "Thermals & noise", "loud": "Thermals & noise",
    "noise": "Thermals & noise", "silent": "Thermals & noise", "quiet": "Thermals & noise",
    "build": "Build quality", "sturdy": "Build quality", "premium": "Build quality",
    "metal": "Build quality", "plastic": "Build quality", "tank": "Build quality",
    "comfort": "Comfort & fit", "comfortable": "Comfort & fit", "light": "Comfort & fit",
    "heavy": "Comfort & fit", "bulky": "Comfort & fit", "weight": "Comfort & fit",
    "price": "Value for money", "value": "Value for money", "cheap": "Value for money",
    "expensive": "Value for money", "budget": "Value for money",
    "worth": "Value for money", "money": "Value for money",
    "sound": "Sound quality", "bass": "Sound quality", "vocal": "Sound quality",
    "audio": "Sound quality", "speakers": "Sound quality",
    "update": "Software & updates", "app": "Software & updates",
    "ios": "Software & updates", "android": "Software & updates",
    "menu": "Software & updates", "menus": "Software & updates",
    "call": "Calls & microphone", "mic": "Calls & microphone",
    "calls": "Calls & microphone",
    "gps": "GPS & tracking", "tracking": "GPS & tracking",
    "steps": "GPS & tracking", "sleep": "GPS & tracking",
    "keyboard": "Keyboard & input", "touch": "Keyboard & input",
    "trackpad": "Keyboard & input",
    "port": "Ports & connectivity", "ports": "Ports & connectivity",
    "bluetooth": "Ports & connectivity", "usb": "Ports & connectivity",
    "wifi": "Ports & connectivity",
}


def _sentiment_of(text: str) -> str:
    tokens = set(re.findall(r"[a-z']+", text.lower()))
    pos = len(tokens & POS_WORDS)
    neg = len(tokens & NEG_WORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _extract_themes_fallback(
    reviews: list[ProductReview],
) -> tuple[list[ReviewTheme], list[ReviewTheme], list[str], str]:
    pos_buckets: dict[str, list[ProductReview]] = defaultdict(list)
    neg_buckets: dict[str, list[ProductReview]] = defaultdict(list)
    complaint_counter: Counter[str] = Counter()

    for rev in reviews:
        text = f"{rev.title or ''} {rev.body}".lower()
        tokens = set(re.findall(r"[a-z']+", text))
        matched_themes = {
            theme for kw, theme in THEME_LEXICON.items() if kw in tokens
        }
        for theme in matched_themes:
            if _sentiment_of(text) == "positive":
                pos_buckets[theme].append(rev)
            elif _sentiment_of(text) == "negative":
                neg_buckets[theme].append(rev)
                complaint_counter[theme] += 1
            else:
                # neutral sentences mentioning a theme count as mild signal
                pos_buckets[theme].append(rev)

    def _to_themes(buckets: dict[str, list[ProductReview]], limit: int = 5) -> list[ReviewTheme]:
        out = []
        for theme, revs in sorted(buckets.items(), key=lambda kv: -len(kv[1]))[:limit]:
            quote = next(
                (r.body for r in revs if _sentiment_of(
                    f"{r.title or ''} {r.body}") != "neutral"),
                revs[0].body,
            )
            out.append(ReviewTheme(
                theme=theme,
                sentiment="positive" if buckets is pos_buckets else "negative",
                mentions=len(revs),
                example_quote=quote[:240],
            ))
        return out

    positive = _to_themes(pos_buckets)
    negative = _to_themes(neg_buckets)
    complaints = [t for t, _ in complaint_counter.most_common(4)]

    avg = _avg_rating(reviews)
    summary = (
        f"Analysis of {len(reviews)} customer review(s)"
        + (f" averaging {avg:.1f}/5." if avg else ".")
        + f" Most praised: {', '.join(t.theme for t in positive[:3]) or 'no clear themes'}."
        + f" Main complaints: {', '.join(complaints[:3]) or 'none recurring'}."
    )
    return positive, negative, complaints, summary


def _avg_rating(reviews: list[ProductReview]) -> float:
    vals = [r.rating for r in reviews if r.rating is not None]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def _reliability_concerns(negative: list[ReviewTheme],
                          complaints: list[str]) -> list[str]:
    """Flag only evidence-backed concerns (recurring negative themes)."""
    concerns = []
    for t in negative:
        if t.mentions >= 2 and t.sentiment == "negative":
            concerns.append(
                f"Recurring complaint: {t.theme.lower()} mentioned in {t.mentions} reviews."
            )
    return concerns[:4]


# --- public API -------------------------------------------------------------

async def analyze_product_reviews(
    db: Session, product: Product
) -> ReviewAnalysisResponse:
    reviews = list(db.scalars(
        select(ProductReview).where(ProductReview.product_id == product.id)
    ).all())

    if not reviews:
        return ReviewAnalysisResponse(
            product_id=product.id,
            product_title=product.title,
            review_count=0,
            average_rating=product.rating,
            summary=(
                "No customer reviews are available for this product in our data "
                "providers, so no sentiment analysis can be performed."
            ),
            is_sample_data=product.is_sample_data,
            llm_mode="not_applicable",
        )

    # Try the LLM path first; fall back to the deterministic extractor.
    llm_mode = "rule-based-fallback"
    positive: list[ReviewTheme] = []
    negative: list[ReviewTheme] = []
    complaints: list[str] = []
    summary = ""

    # Attempt a structured LLM analysis of the real review corpus; on any
    # failure `structured_completion` degrades and we use the fallback below.
    corpus = "\n\n".join(
        f"- [{r.rating or '?'}★] {r.title or ''}: {r.body}" for r in reviews[:40]
    )
    result = await structured_completion(
        system=(
            "You are a shopping research analyst. Analyze ONLY the customer "
            "reviews provided. Extract positive themes, negative themes, "
            "recurring complaints and a 2-sentence summary. Never invent "
            "reviews or statistics."
        ),
        user=f"PRODUCT: {product.title}\n\nREVIEWS:\n{corpus}",
        schema=LLMThemeOutput,
        fallback=None,
    )
    if result.data is not None:
        llm_mode = result.mode
        data: LLMThemeOutput = result.data
        positive = [
            ReviewTheme(theme=t.get("theme", "Other"), sentiment="positive",
                        mentions=int(t.get("mentions", 1)),
                        example_quote=t.get("example_quote"))
            for t in data.positive_themes
        ]
        negative = [
            ReviewTheme(theme=t.get("theme", "Other"), sentiment="negative",
                        mentions=int(t.get("mentions", 1)),
                        example_quote=t.get("example_quote"))
            for t in data.negative_themes
        ]
        complaints = [c for c in data.reliability_concerns][:4] or [
            t.theme for t in negative
        ]
        summary = data.summary or ""

    if not summary:
        positive, negative, complaints, summary = _extract_themes_fallback(reviews)
        llm_mode = "rule-based-fallback"

    return ReviewAnalysisResponse(
        product_id=product.id,
        product_title=product.title,
        review_count=len(reviews),
        average_rating=_avg_rating(reviews) or product.rating,
        positive_themes=positive,
        negative_themes=negative,
        recurring_complaints=complaints,
        summary=summary,
        reliability_concerns=_reliability_concerns(negative, complaints),
        is_sample_data=product.is_sample_data,
        llm_mode=llm_mode,
    )
