"""Conditional routing for the shopping graph.

The router inspects the classified intent and schedules ONLY the branches
that query needs. Independent branches (discovery + review analysis) are
returned together so LangGraph executes them in parallel in one super-step.
"""

import logging
from typing import Any

from app.graph.state import ShoppingState

logger = logging.getLogger("shopmate.graph.routing")

# Branch entry nodes
SEARCH = "search_node"
COMPARE = "compare_node"
REVIEW = "review_node"
SPEC = "spec_node"
RECOMMEND = "recommend_node"
ADVISE = "advise_node"


def route_intent(state: ShoppingState) -> list[str] | str:
    """Map the classified intent to the branch nodes that must run.

    Returns either a single node name or a list of node names (fan-out →
    LangGraph runs them in parallel within the same super-step).
    """
    intent = state.get("intent") or (state.get("understanding") or {}).get(
        "intent", "product_search"
    )
    understanding = state.get("understanding") or {}
    targets = understanding.get("target_product_ids") or []
    has_products = bool(state.get("products"))
    has_comparison = bool(state.get("comparison"))

    if intent == "product_search":
        # Discovery first; also analyse reviews when the user pointed at
        # specific products (e.g. "is SMP-LAP-001 worth buying?").
        return [SEARCH, REVIEW] if targets else SEARCH

    if intent == "recommendation":
        return [SEARCH, REVIEW] if targets else SEARCH

    if intent == "product_compare":
        # Price/spec comparison always needs the compare branch; review
        # analysis fans out in parallel when target products are known.
        return [COMPARE, REVIEW] if targets else COMPARE

    if intent == "price_compare":
        return COMPARE

    if intent == "review_analysis":
        # Known products → analyse them directly; otherwise discover first.
        if targets or has_products:
            return REVIEW
        return SEARCH  # will flow into spec → recommend → advise with reviews

    if intent == "general_shopping_advice":
        # "Is this worth buying?" → review + spec evidence for known targets.
        if targets or has_comparison:
            return [REVIEW] if targets and not has_comparison else COMPARE
        return SEARCH

    # general_qa / unknown → advisor answers from context alone.
    return ADVISE


def after_branch(state: ShoppingState) -> str:
    """All stage-2 branches converge on specification analysis."""
    return SPEC


def after_spec(state: ShoppingState) -> str:
    """Skip the ranking stage for intents where it adds nothing.

    review_analysis and price_compare already produced their own verdict
    (review summary / cheapest listing); re-ranking would be wasted work.
    """
    intent = state.get("intent") or "product_search"
    if intent in ("review_analysis", "price_compare"):
        return ADVISE
    if not (state.get("products") or state.get("comparison")):
        # Nothing to rank — go straight to the advisor with whatever exists.
        return ADVISE
    return RECOMMEND


def has_target_products(state: ShoppingState) -> bool:
    u = state.get("understanding") or {}
    return bool(u.get("target_product_ids"))
