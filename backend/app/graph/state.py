"""Typed LangGraph state for the shopping research workflow.

Every node reads/writes this shared state. All values are JSON-serialisable
so the SQLAlchemy checkpointer can persist and resume a research run.

`trace` and `errors` use `Annotated[..., operator.add]` reducers because the
router can fan out multiple branch nodes in the same super-step; each branch
contributes its own entries instead of overwriting the list.
"""

import operator
from typing import Annotated, Any, Literal, Optional, TypedDict


class Understanding(TypedDict, total=False):
    """Output of the Query Understanding agent (Pydantic-validated)."""

    intent: Literal[
        "product_search",
        "product_compare",
        "review_analysis",
        "recommendation",
        "price_compare",
        "general_shopping_advice",
        "general_qa",
    ]
    category: Optional[str]
    budget_min: Optional[float]
    budget_max: Optional[float]
    currency: str
    usage: list[str]
    requirements: dict[str, Any]
    preferences: dict[str, Any]
    target_product_ids: list[str]
    missing_information: list[str]
    followup_question: Optional[str]
    resolved_query: str  # query with conversation context applied


class ShoppingState(TypedDict, total=False):
    # --- inputs ---
    query: str
    user_id: Optional[str]
    conversation_id: Optional[str]
    history: list[dict[str, str]]  # [{"role":..., "content":...}]
    prior_context: dict[str, Any]  # rolling memory from previous turns

    # --- stage 1: understanding ---
    understanding: Understanding
    intent: str
    llm_mode: str

    # --- stage 2: branch outputs ---
    products: list[dict[str, Any]]          # normalised product dicts
    provider_errors: list[str]
    is_sample_data: bool
    comparison: Optional[dict[str, Any]]
    review_analysis: Optional[dict[str, Any]]

    # --- stage 3: downstream analysis ---
    spec_analysis: Optional[dict[str, Any]]
    ranked: list[dict[str, Any]]
    weights: dict[str, float]

    # --- final ---
    final_response: str
    suggested_followups: list[str]

    # --- bookkeeping ---
    # Reducer = append: parallel branch nodes each contribute their entries.
    trace: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
    # Which branch nodes the router scheduled (for convergence logic)
    active_branches: list[str]


DEFAULT_STATE_KEYS: dict[str, Any] = {
    "history": [],
    "prior_context": {},
    "products": [],
    "provider_errors": [],
    "is_sample_data": False,
    "comparison": None,
    "review_analysis": None,
    "spec_analysis": None,
    "ranked": [],
    "weights": {},
    "final_response": "",
    "suggested_followups": [],
    "trace": [],
    "errors": [],
    "active_branches": [],
    "llm_mode": "unknown",
    "intent": "product_search",
}


def initial_state(**overrides: Any) -> ShoppingState:
    """Build a well-formed starting state."""
    state: ShoppingState = dict(DEFAULT_STATE_KEYS)  # type: ignore[assignment]
    state.update(overrides)
    return state
