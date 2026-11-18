"""Agent 1 — Query Understanding Agent.

Extracts a structured shopping intent from natural language using Pydantic
structured output. When an LLM is configured it drives the extraction;
otherwise a deterministic rule-based extractor runs (regex/heuristics over
the real query + conversation memory) — never a hardcoded answer.
"""

import logging
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.services.llm_service import structured_completion

logger = logging.getLogger("shopmate.agents.query")

VALID_INTENTS = (
    "product_search",
    "product_compare",
    "review_analysis",
    "recommendation",
    "price_compare",
    "general_shopping_advice",
    "general_qa",
)


class QueryUnderstanding(BaseModel):
    """Structured output contract of the query agent."""

    intent: str = "product_search"
    category: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str = "INR"
    usage: list[str] = Field(default_factory=list)
    requirements: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    target_product_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    followup_question: Optional[str] = None
    resolved_query: str = ""


CATEGORY_KEYWORDS = {
    "laptop": ["laptop", "notebook", "ultrabook", "gaming laptop"],
    "smartphone": ["smartphone", "phone", "iphone", "galaxy", "mobile phone"],
    "headphones": ["headphone", "earbud", "earbuds", "headset", "earphone"],
    "smartwatch": ["smartwatch", "watch", "fitness band"],
    "tablet": ["tablet", "ipad", "pad"],
    "camera": ["camera", "mirrorless", "dslr"],
}

USAGE_KEYWORDS = {
    "programming": ["programming", "coding", "developer", "software", "compile",
                    "development", "code"],
    "gaming": ["gaming", "games", "game", "esports", "aaa titles"],
    "video_editing": ["video edit", "editing", "premiere", "render"],
    "photo_editing": ["photo edit", "photoshop", "retouch"],
    "student": ["student", "study", "college", "school", "university", "classes"],
    "work": ["work", "office", "business", "meetings", "professional"],
    "travel": ["travel", "traveling", "portable", "commute"],
    "fitness": ["fitness", "workout", "running", "gym", "health", "sleep tracking"],
    "music": ["music", "listening", "podcast", "audio"],
    "calls": ["calls", "calling", "meeting audio", "conference"],
    "content_creation": ["content creation", "streaming", "youtube", "podcasting"],
}

REQUIREMENT_RULES: list[tuple[str, re.Pattern, Any]] = [
    ("ram_min", re.compile(r"(\d+)\s*(?:gb\s*)?ram|ram\s*(?:of\s*)?(\d+)\s*gb",
                           re.I), "ram"),
    ("storage_min", re.compile(r"(\d+)\s*(?:gb|tb)\s*(?:ssd|storage)|"
                               r"(?:ssd|storage)\s*(?:of\s*)?(\d+)\s*(?:gb|tb)",
                               re.I), "storage"),
    ("battery_min_hours", re.compile(r"(\d+)\s*[- ]?hour battery|battery\s*(?:lasts\s*)?"
                                     r"(\d+)\s*hours", re.I), "hours"),
    ("camera_min_mp", re.compile(r"(\d+)\s*mp camera|(\d+)\s*megapixel", re.I), "camera"),
]

NUMBER_WORDS = {
    "five": 5, "six": 6, "seven": 7, "eight": 8, "ten": 10, "sixteen": 16,
    "thirty two": 32, "thirty-two": 32,
}


def _extract_budget(text: str) -> tuple[Optional[float], Optional[float]]:
    """Parse budgets like 'under ₹60,000', 'below 60000', 'between 30k and 60k'."""
    t = text.replace(",", "")
    max_budget: Optional[float] = None
    min_budget: Optional[float] = None

    m = re.search(
        r"(?:under|below|within|less than|max(?:imum)?|upto|up to|budget(?: of)?)\s*"
        r"(?:inr|rs\.?|₹|inr\.?)?\s*([0-9]+(?:\.[0-9]+)?)\s*(k|thousand|lakh|l)?",
        t, re.I,
    )
    if m:
        max_budget = _to_number(m.group(1), m.group(2))
    else:
        m2 = re.search(
            r"(?:between|from)\s*(?:inr|rs\.?|₹)?\s*([0-9]+(?:\.[0-9]+)?)\s*"
            r"(k|thousand|lakh|l)?\s*(?:and|to|-)\s*(?:inr|rs\.?|₹)?\s*"
            r"([0-9]+(?:\.[0-9]+)?)\s*(k|thousand|lakh|l)?",
            t, re.I,
        )
        if m2:
            min_budget = _to_number(m2.group(1), m2.group(2))
            max_budget = _to_number(m2.group(3), m2.group(4))

    if max_budget is None:
        # bare "60000 budget" / "60k laptop"
        m3 = re.search(r"(?:₹|rs\.?|inr)?\s*(\d{2,6})\s*(k)?\s*(?:budget|laptop|phone|"
                       r"headphones|smartwatch|tablet)?", t, re.I)
        if m3 and ("budget" in t.lower() or m3.group(2)):
            max_budget = _to_number(m3.group(1), m3.group(2))
    return min_budget, max_budget


def _to_number(raw: str, suffix: Optional[str]) -> Optional[float]:
    try:
        val = float(raw)
    except ValueError:
        return None
    s = (suffix or "").lower()
    if s in ("k", "thousand"):
        val *= 1000
    elif s in ("lakh", "l"):
        val *= 100000
    return val


def _detect_category(text: str) -> Optional[str]:
    low = text.lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        # Word boundaries: "headphones" must not be captured as "phone".
        if any(re.search(rf"\b{re.escape(w)}s?\b", low) for w in words):
            return cat
    return None


def _detect_usage(text: str) -> list[str]:
    low = text.lower()
    return [u for u, words in USAGE_KEYWORDS.items() if any(w in low for w in words)]


def _detect_requirements(text: str) -> dict[str, Any]:
    reqs: dict[str, Any] = {}
    low = text.lower()
    if re.search(r"\b(?:dedicated|discrete)\s+gpu|\bgpu\b|rtx|graphics card", low):
        reqs["gpu_required"] = True
    m = re.search(r"(\d+)\s*gb\s*ram|ram\s*(?:of\s*)?(\d+)\s*gb", low)
    if m:
        reqs["ram_min"] = int(m.group(1) or m.group(2))
    m = re.search(r"(\d+)\s*tb\s*(?:ssd|storage)", low)
    if m:
        reqs["storage_min"] = int(m.group(1)) * 1024
    else:
        m = re.search(r"(\d+)\s*gb\s*(?:ssd|storage)", low)
        if m:
            reqs["storage_min"] = int(m.group(1))
    m = re.search(r"(\d+)\s*[- ]?hour battery|battery\s*(?:lasts\s*)?(\d+)\s*hours", low)
    if m:
        reqs["battery_min_hours"] = int(m.group(1) or m.group(2))
    m = re.search(r"(\d+)\s*(?:mp|megapixel)\s*camera", low)
    if m:
        reqs["camera_min_mp"] = int(m.group(1))
    if re.search(r"\bamoled\b|\boled\b", low):
        reqs["display"] = "OLED"
    return reqs


def _detect_intent(text: str) -> str:
    low = text.lower()
    if re.search(r"\bcompare\b|\bdifference between\b|\bvs\.?\b|\bversus\b", low):
        # "compare prices" is a price comparison; otherwise product compare
        if "price" in low and "spec" not in low and "better" not in low:
            return "price_compare"
        return "product_compare"
    if re.search(r"\breview|complaints?|sentiment|what do (?:people|customers) say\b", low):
        return "review_analysis"
    if re.search(r"worth (?:buying|purchasing)|should i buy|is it good|reliable\??", low):
        return "general_shopping_advice"
    if re.search(r"cheaper alternativ|alternative to|other options like|instead of", low):
        return "recommendation"
    if re.search(r"recommend|best value|value for money|suggest|which one should i", low):
        return "recommendation"
    if re.search(r"find|search|show|looking for|need|want|buy|best", low):
        return "product_search"
    return "general_qa"


def _detect_products(text: str, prior: dict[str, Any]) -> list[str]:
    """Product ids already in play (SMP-xxx or internal uuids)."""
    ids = set(re.findall(r"\bSMP-[A-Z]{3}-\d{3}\b", text))
    for key in ("target_product_ids", "last_product_ids"):
        for v in prior.get(key) or []:
            if isinstance(v, str):
                ids.add(v)
    # internal UUIDs (36 chars with dashes)
    ids.update(re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                          text))
    return sorted(ids)


def rule_based_extract(query: str, prior_context: dict[str, Any]) -> QueryUnderstanding:
    """Deterministic extraction used when no LLM is reachable."""
    budget_min, budget_max = _extract_budget(query)
    # Conversation memory fills gaps the current turn doesn't restate.
    if budget_max is None:
        budget_max = prior_context.get("budget_max")
    if budget_min is None:
        budget_min = prior_context.get("budget_min")

    category = _detect_category(query) or prior_context.get("category")
    usage = _detect_usage(query)
    for u in prior_context.get("usage") or []:
        if u not in usage:
            usage.append(u)

    requirements = dict(prior_context.get("requirements") or {})
    requirements.update(_detect_requirements(query))

    preferences = dict(prior_context.get("preferences") or {})
    if "budget" not in preferences and budget_max:
        preferences["budget"] = budget_max

    intent = _detect_intent(query)

    # Context-aware reclassification: a follow-up like "what about one with
    # better battery life?" has no category keyword of its own but clearly
    # continues the previous shopping research (prior context has a category).
    if intent == "general_qa" and prior_context.get("category"):
        if re.search(r"\b(better|another|one with|also|else|instead|cheaper|"
                     r"faster|longer|alternative|option)\b", query, re.I):
            intent = "product_search"
        # Pure usage/clarification answers ("Programming and gaming") also
        # continue the research when the conversation already has a category.
        elif usage and not _extract_budget(query)[1]:
            intent = "product_search"

    # A concrete product category in the CURRENT turn ("laptop under 60000
    # for coding") is shopping intent even without a verb like "find" — but
    # genuine questions ("what is a laptop?") stay general Q&A.
    if intent == "general_qa" and _detect_category(query):
        stripped = query.strip()
        is_question = bool(
            re.match(r"^(what|why|how|when|who|where|explain|define|tell)\b",
                     stripped, re.I)
            or stripped.endswith("?")
        )
        if not is_question or budget_max is not None or usage or requirements:
            intent = "product_search"

    # Gaming implies a discrete GPU matters for this search.
    if "gaming" in usage and "gpu_required" not in requirements:
        requirements["gpu_required"] = True

    # Compare intent: collect the two+ product names being compared.
    target_ids = _detect_products(query, prior_context)

    missing: list[str] = []
    if intent in ("product_search", "recommendation") and not category:
        missing.append("product category")
    if intent in ("product_search", "recommendation") and budget_max is None:
        missing.append("budget")

    followup = None
    if intent == "product_search" and not category:
        followup = "What type of product are you looking for (laptop, phone, headphones…)?"
    elif intent == "product_search" and budget_max is None:
        followup = "What is your maximum budget?"

    return QueryUnderstanding(
        intent=intent,
        category=category,
        budget_min=budget_min,
        budget_max=budget_max,
        currency=str(prior_context.get("currency") or "INR"),
        usage=usage,
        requirements=requirements,
        preferences=preferences,
        target_product_ids=target_ids,
        missing_information=missing,
        followup_question=followup,
        resolved_query=query,
    )


class QueryUnderstandingAgent:
    """Agent 1: understand intent, budget, specs, usage and context."""

    name = "query_understanding"

    async def run(
        self, query: str, history: Optional[list[dict]] = None,
        prior_context: Optional[dict[str, Any]] = None,
    ) -> tuple[QueryUnderstanding, str]:
        """Returns (understanding, llm_mode)."""
        prior_context = prior_context or {}
        fallback = rule_based_extract(query, prior_context)

        # Give the model the conversation memory so it can resolve pronouns
        # ("this laptop") and preserve earlier constraints.
        memory_lines = []
        for k in ("category", "budget_min", "budget_max", "currency", "usage",
                  "requirements", "preferences"):
            if prior_context.get(k):
                memory_lines.append(f"{k}: {prior_context[k]}")
        recent = (history or [])[-6:]
        if recent:
            memory_lines.append(
                "recent: " + " | ".join(f"{m.get('role')}: {m.get('content', '')[:120]}"
                                        for m in recent)
            )
        memory = "\n".join(memory_lines) or "(none)"

        result = await structured_completion(
            system=(
                "You are the query understanding agent of a shopping research "
                "platform. Extract the shopping intent as JSON. Preserve earlier "
                "constraints from memory; only change them if the user explicitly "
                "does. intent must be one of: " + ", ".join(VALID_INTENTS) + "."
            ),
            user=f"MEMORY:\n{memory}\n\nUSER QUERY:\n{query}",
            schema=QueryUnderstanding,
            fallback=fallback,
        )
        understanding = result.data or fallback
        if understanding.intent not in VALID_INTENTS:
            understanding.intent = fallback.intent
        if not understanding.resolved_query:
            understanding.resolved_query = query
        return understanding, result.mode
