"""LangGraph nodes — thin wrappers that invoke one agent each.

Each node:
  * reads only what it needs from the typed state,
  * records a trace entry (agent, status, timing),
  * catches its own exceptions so a single failing agent degrades instead of
    killing the whole research run.

The database session is supplied per-invocation via the graph `config`
(`configurable={"db": session}`) — never stored in checkpointed state.
"""

import logging
import time
from typing import Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from app.agents import (
    PriceComparisonAgent,
    ProductDiscoveryAgent,
    QueryUnderstandingAgent,
    RecommendationAgent,
    ReviewAnalysisAgent,
    ShoppingAdvisorAgent,
    SpecificationAnalysisAgent,
)
from app.graph.state import ShoppingState

logger = logging.getLogger("shopmate.graph.nodes")


def _db(config: RunnableConfig | dict[str, Any]) -> Session:
    db = (config or {}).get("configurable", {}).get("db")
    if db is None:
        raise RuntimeError("graph config is missing the database session")
    return db


def _trace(state: ShoppingState, agent: str, status: str, started: float,
           detail: str | None = None) -> list[dict[str, Any]]:
    """New trace entry only — `trace` uses an append reducer."""
    _ = state  # signature kept for readability at call sites
    return [{
        "agent": agent,
        "status": status,
        "detail": detail,
        "took_ms": int((time.perf_counter() - started) * 1000),
    }]


def _errors(state: ShoppingState, *msgs: str) -> list[str]:
    """New error strings only — `errors` uses an append reducer."""
    _ = state
    return [m for m in msgs if m]


def _comparison_products(state: ShoppingState) -> list[dict[str, Any]]:
    """Products from a comparison payload (compare intent ranks only those)."""
    comparison = state.get("comparison") or {}
    return list(comparison.get("products") or [])


# ---------------------------------------------------------------- stage 1 --

async def understand_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Agent 1: classify intent + extract budget/specs/usage with memory."""
    started = time.perf_counter()
    agent = QueryUnderstandingAgent()
    try:
        understanding, llm_mode = await agent.run(
            query=state.get("query", ""),
            history=state.get("history") or [],
            prior_context=state.get("prior_context") or {},
        )
        # Resolve product references (names or ids) in compare/review intents
        # to internal ids so downstream agents can read real records.
        if understanding.intent in ("product_compare", "price_compare",
                                    "review_analysis"):
            from app.services.product_service import resolve_targets_from_text

            try:
                targets = await resolve_targets_from_text(
                    _db(config), understanding.resolved_query or state.get("query", "")
                )
                if targets:
                    understanding.target_product_ids = targets
            except Exception:
                logger.exception("target_resolution_failed")
        return {
            "understanding": understanding.model_dump(mode="json"),
            "intent": understanding.intent,
            "llm_mode": llm_mode,
            "trace": _trace(state, agent.name, "ok", started,
                            f"intent={understanding.intent}"),
        }
    except Exception as exc:  # degrade to a minimal understanding, keep going
        logger.exception("understand_node_failed")
        fallback = {
            "intent": "product_search",
            "resolved_query": state.get("query", ""),
            "currency": "INR",
            "usage": [],
            "requirements": {},
            "preferences": {},
            "missing_information": [],
        }
        return {
            "understanding": fallback,  # type: ignore[arg-type]
            "intent": "product_search",
            "llm_mode": "rule-based-fallback",
            "trace": _trace(state, agent.name, "error", started, str(exc)),
            "errors": _errors(state, f"Query understanding failed: {exc}"),
        }


# ---------------------------------------------------------------- stage 2 --

async def search_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Agent 2: discover products from providers (budget + spec filtered)."""
    started = time.perf_counter()
    agent = ProductDiscoveryAgent()
    u = state.get("understanding") or {}
    try:
        result = await agent.run(
            db=_db(config),
            query=u.get("resolved_query") or state.get("query", ""),
            category=u.get("category"),
            budget_min=u.get("budget_min"),
            budget_max=u.get("budget_max"),
            requirements=u.get("requirements") or {},
            limit=12,
        )
        # State must be JSON-serialisable for the checkpoint store.
        products = [p.model_dump(mode="json") if hasattr(p, "model_dump") else p
                    for p in result["products"]]
        return {
            "products": products,
            "provider_errors": result["provider_errors"],
            "is_sample_data": result["is_sample_data"],
            "trace": _trace(state, agent.name, "ok", started,
                            f"found={len(products)} dropped="
                            f"{result['dropped_by_requirements']}"),
            "errors": _errors(state, *result["provider_errors"]),
        }
    except Exception as exc:
        logger.exception("search_node_failed")
        return {
            "products": [],
            "trace": _trace(state, agent.name, "error", started, str(exc)),
            "errors": _errors(state, f"Product discovery failed: {exc}"),
        }


async def compare_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Agent 3: merchant price comparison + freshness for target products."""
    started = time.perf_counter()
    agent = PriceComparisonAgent()
    u = state.get("understanding") or {}
    try:
        result = await agent.run(
            db=_db(config),
            product_ids=u.get("target_product_ids") or [],
            products_hint=state.get("products") or [],
        )
        status = "ok" if result.get("comparison") else "error"
        return {
            "comparison": result.get("comparison"),
            "trace": _trace(state, agent.name, status, started,
                            f"price_diff={result.get('price_difference')}"),
            "errors": _errors(state, *result.get("errors", [])),
        }
    except Exception as exc:
        logger.exception("compare_node_failed")
        return {
            "comparison": None,
            "trace": _trace(state, agent.name, "error", started, str(exc)),
            "errors": _errors(state, f"Price comparison failed: {exc}"),
        }


async def review_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Agent 4: analyse ACTUAL provider-supplied reviews."""
    started = time.perf_counter()
    agent = ReviewAnalysisAgent()
    u = state.get("understanding") or {}
    try:
        result = await agent.run(
            db=_db(config),
            product_ids=u.get("target_product_ids") or [],
            products_hint=state.get("products") or [],
        )
        status = "ok" if result.get("review_analysis") else "error"
        return {
            "review_analysis": result.get("review_analysis"),
            "trace": _trace(state, agent.name, status, started,
                            f"analysed={bool(result.get('review_analysis'))}"),
            "errors": _errors(state, *result.get("errors", [])),
        }
    except Exception as exc:
        logger.exception("review_node_failed")
        return {
            "review_analysis": None,
            "trace": _trace(state, agent.name, "error", started, str(exc)),
            "errors": _errors(state, f"Review analysis failed: {exc}"),
        }


async def compare_prices_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Alias branch for the `price_compare` intent (same agent as compare)."""
    return await compare_node(state, config)


# ---------------------------------------------------------------- stage 3 --

async def spec_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Agent 5: specification comparison across candidates."""
    started = time.perf_counter()
    agent = SpecificationAnalysisAgent()
    u = state.get("understanding") or {}
    products = state.get("products") or []
    if not products and state.get("comparison"):
        products = (state.get("comparison") or {}).get("products") or []
    if not products:
        return {
            "trace": _trace(state, agent.name, "skipped", started, "no products"),
        }
    # Normalise id field: search results use `id`, comparison rows use `id` too,
    # but the agent contract is `product_id`.
    products = [
        dict(p, product_id=p.get("product_id") or p.get("id"))
        if isinstance(p, dict) else p
        for p in products
    ]
    try:
        result = await agent.run(
            products=products,
            requirements=u.get("requirements") or {},
            category=u.get("category"),
        )
        return {
            "spec_analysis": result.get("spec_analysis"),
            "trace": _trace(state, agent.name, "ok", started),
        }
    except Exception as exc:
        logger.exception("spec_node_failed")
        return {
            "trace": _trace(state, agent.name, "error", started, str(exc)),
            "errors": _errors(state, f"Specification analysis failed: {exc}"),
        }


async def recommend_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Agent 6: hybrid, explainable ranking of the candidates."""
    started = time.perf_counter()
    agent = RecommendationAgent()
    u = state.get("understanding") or {}
    try:
        result = await agent.run(
            db=_db(config),
            query=u.get("resolved_query") or state.get("query", ""),
            products=state.get("products") or _comparison_products(state),
            category=u.get("category"),
            budget_max=u.get("budget_max"),
            budget_min=u.get("budget_min"),
            requirements=u.get("requirements") or {},
            usage=u.get("usage") or [],
            preferences=u.get("preferences") or {},
            limit=6,
        )
        return {
            "ranked": result["ranked"],
            "weights": result["weights"],
            "trace": _trace(state, agent.name, "ok", started,
                            f"ranked={len(result['ranked'])}"),
        }
    except Exception as exc:
        logger.exception("recommend_node_failed")
        return {
            "ranked": [],
            "trace": _trace(state, agent.name, "error", started, str(exc)),
            "errors": _errors(state, f"Recommendation failed: {exc}"),
        }


async def advise_node(state: ShoppingState, config: RunnableConfig) -> ShoppingState:
    """Agent 7: combine everything into the final shopping advice."""
    started = time.perf_counter()
    agent = ShoppingAdvisorAgent()
    # Multi-product review analysis wraps results as {"items": [...]} — unwrap
    # so the advisor always sees a single analysis object.
    review_analysis = state.get("review_analysis")
    if isinstance(review_analysis, dict) and "items" in review_analysis:
        items = review_analysis.get("items") or []
        review_analysis = items[0] if items else None
    try:
        result = await agent.run(
            understanding=state.get("understanding") or {},
            ranked=state.get("ranked") or [],
            comparison=state.get("comparison"),
            review_analysis=review_analysis,
            spec_analysis=state.get("spec_analysis"),
            provider_errors=state.get("provider_errors") or [],
            is_sample_data=bool(state.get("is_sample_data")),
            intent=state.get("intent", "product_search"),
        )
        return {
            "final_response": result["final_response"],
            "suggested_followups": result["suggested_followups"],
            "trace": _trace(state, agent.name, "ok", started),
        }
    except Exception as exc:
        logger.exception("advise_node_failed")
        # Last-resort reply built from raw state (still not hardcoded).
        products = state.get("products") or []
        lines = ["I hit an error while composing the final advice."]
        for p in products[:3]:
            lines.append(f"- {p.get('title')} — ₹{p.get('price', 0):,.0f}")
        lines.append(f"(technical: {exc})")
        return {
            "final_response": "\n".join(lines),
            "suggested_followups": ["Retry the search", "Compare these products"],
            "trace": _trace(state, agent.name, "error", started, str(exc)),
            "errors": _errors(state, f"Advisor failed: {exc}"),
        }
