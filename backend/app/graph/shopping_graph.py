"""The ShopMate AI shopping research StateGraph.

    USER QUERY
        |
        v
    QUERY UNDERSTANDING  (agent 1)
        |
        v
    INTENT CLASSIFICATION + CONDITIONAL ROUTER
        |
        +----------------+-----------------+
        v                v                 v
    DISCOVERY (2)   PRICE COMPARE (3)  REVIEW ANALYSIS (4)   <- parallel fan-out
        |                |                 |
        +----------------+-----------------+
                         v
          SPECIFICATION ANALYSIS (5)
                         |
                         v (conditional: skip ranking when pointless)
          RECOMMENDATION ENGINE (6)
                         |
                         v
             SHOPPING ADVISOR (7)
                         |
                         v
                 FINAL RESPONSE

- Conditional edges decide which branches run (no agent is called needlessly).
- Independent branches run in parallel via list-fan-out from the router.
- Every node catches its own errors; the graph always reaches the advisor.
- Checkpoints persist through PostgreSQL/SQLite (graph/checkpointer.py).
"""

import logging
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.database.connection import SessionLocal
from app.graph import nodes, routing
from app.graph.checkpointer import get_checkpointer
from app.graph.state import ShoppingState, initial_state

logger = logging.getLogger("shopmate.graph")


def build_graph(checkpointer: Optional[Any] = None):
    """Compile the shopping research graph (pure function — easy to test)."""
    builder = StateGraph(ShoppingState)

    # --- nodes ------------------------------------------------------------
    builder.add_node("understand_node", nodes.understand_node)
    builder.add_node(routing.SEARCH, nodes.search_node)
    builder.add_node(routing.COMPARE, nodes.compare_node)
    builder.add_node(routing.REVIEW, nodes.review_node)
    builder.add_node(routing.SPEC, nodes.spec_node)
    builder.add_node(routing.RECOMMEND, nodes.recommend_node)
    builder.add_node(routing.ADVISE, nodes.advise_node)

    # --- edges ------------------------------------------------------------
    builder.add_edge(START, "understand_node")

    # Intent classification → conditional branch selection (fan-out allowed).
    builder.add_conditional_edges(
        "understand_node",
        routing.route_intent,
        [
            routing.SEARCH, routing.COMPARE, routing.REVIEW, routing.ADVISE,
        ],
    )

    # All stage-2 branches converge on specification analysis.
    builder.add_conditional_edges(
        routing.SEARCH, routing.after_branch, [routing.SPEC]
    )
    builder.add_conditional_edges(
        routing.COMPARE, routing.after_branch, [routing.SPEC]
    )
    builder.add_conditional_edges(
        routing.REVIEW, routing.after_branch, [routing.SPEC]
    )

    # spec → (recommend | advise) depending on intent.
    builder.add_conditional_edges(
        routing.SPEC, routing.after_spec, [routing.RECOMMEND, routing.ADVISE]
    )

    builder.add_edge(routing.RECOMMEND, routing.ADVISE)
    builder.add_edge(routing.ADVISE, END)

    return builder.compile(checkpointer=checkpointer)


# Compiled once with the persistent DB checkpointer.
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer=get_checkpointer())
    return _graph


def reset_graph_cache() -> None:
    """Test helper — rebuild the compiled graph (e.g. after DB switch)."""
    global _graph
    _graph = None


async def run_research(
    query: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    prior_context: Optional[dict[str, Any]] = None,
    thread_id: Optional[str] = None,
    db: Optional[Any] = None,
) -> ShoppingState:
    """Invoke the graph for one research turn.

    `db` is passed through `configurable` so nodes share the request's
    session; it is never part of the checkpointed state.
    """
    state = initial_state(
        query=query,
        user_id=user_id,
        conversation_id=conversation_id,
        history=history or [],
        prior_context=prior_context or {},
    )
    owns_session = db is None
    session = db or SessionLocal()
    # Checkpoint thread: unique per research turn unless the caller pins one.
    # Conversation memory flows through `history`/`prior_context` (loaded from
    # the DB by the API), so state never leaks between unrelated queries while
    # each run's checkpoint is still persisted for resume/audit.
    resolved_thread = thread_id or (
        f"{conversation_id}:{__import__('uuid').uuid4().hex[:8]}"
        if conversation_id else f"anon:{__import__('uuid').uuid4().hex[:8]}"
    )
    config: dict[str, Any] = {
        "configurable": {
            "thread_id": resolved_thread,
            "db": session,
        }
    }
    try:
        result = await get_graph().ainvoke(state, config=config)
        return result  # type: ignore[return-value]
    finally:
        if owns_session:
            session.close()
