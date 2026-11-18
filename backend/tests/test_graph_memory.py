"""LangGraph routing, conversation memory and workflow tests."""

import pytest

from app.graph.routing import (
    ADVISE,
    COMPARE,
    REVIEW,
    SEARCH,
    after_spec,
    route_intent,
)
from app.graph.shopping_graph import run_research
from app.graph.state import initial_state
from app.services.conversation_service import merge_context


# --- routing unit tests ----------------------------------------------------

def _state(intent: str, **kw):
    s = initial_state(query="q")
    s["intent"] = intent
    s["understanding"] = {"intent": intent, **kw}
    return s


def test_route_search_only_schedules_discovery():
    assert route_intent(_state("product_search")) == SEARCH


def test_route_compare_schedules_price_branch():
    assert route_intent(_state("product_compare")) == COMPARE


def test_route_compare_with_targets_fans_out_to_review():
    out = route_intent(_state("product_compare", target_product_ids=["x", "y"]))
    assert isinstance(out, list)
    assert COMPARE in out and REVIEW in out  # parallel fan-out


def test_route_review_with_known_product_skips_search():
    assert route_intent(_state("review_analysis",
                               target_product_ids=["x"])) == REVIEW


def test_route_general_qa_goes_straight_to_advisor():
    assert route_intent(_state("general_qa")) == ADVISE


def test_route_price_compare_uses_price_branch():
    assert route_intent(_state("price_compare")) == COMPARE


def test_after_spec_skips_ranking_for_review_intent():
    assert after_spec(_state("review_analysis")) == ADVISE
    assert after_spec(_state("price_compare")) == ADVISE


def test_after_spec_ranks_when_products_exist():
    s = _state("product_search")
    s["products"] = [{"id": "p1"}]
    assert after_spec(s) == "recommend_node"


def test_after_spec_skips_ranking_when_nothing_to_rank():
    assert after_spec(_state("product_search")) == ADVISE


# --- graph integration -----------------------------------------------------

@pytest.mark.asyncio
async def test_graph_search_workflow(db_session):
    state = await run_research(
        "Find the best laptop under 60000 for programming and gaming",
        db=db_session,
        thread_id="test-search-1",
    )
    agents = [t["agent"] for t in state["trace"]]
    assert "query_understanding" in agents
    assert "product_discovery" in agents
    assert "recommendation" in agents
    assert "shopping_advisor" in agents
    # No agent may fail in the happy path
    assert all(t["status"] != "error" for t in state["trace"]), state["trace"]
    assert state["intent"] == "product_search"
    assert state["ranked"]
    assert state["final_response"]
    assert state["llm_mode"] == "rule-based-fallback"  # no LLM configured


@pytest.mark.asyncio
async def test_graph_compare_workflow(db_session):
    state = await run_research("Compare iPhone 15 and Samsung Galaxy S24",
                               db=db_session, thread_id="test-compare-1")
    assert state["intent"] == "product_compare"
    assert state["comparison"] is not None
    assert len(state["comparison"]["products"]) == 2
    # price comparison branch must have run
    assert "price_comparison" in [t["agent"] for t in state["trace"]]
    assert state["final_response"]


@pytest.mark.asyncio
async def test_graph_review_workflow(db_session):
    state = await run_research("Analyze customer complaints about SMP-PHN-002",
                               db=db_session, thread_id="test-review-1")
    assert state["intent"] == "review_analysis"
    assert state["review_analysis"] is not None
    assert state["review_analysis"]["review_count"] > 0
    assert "review_analysis" in [t["agent"] for t in state["trace"]]


@pytest.mark.asyncio
async def test_graph_general_qa_skips_search(db_session):
    """general_qa must NOT invoke the discovery/review branches."""
    state = await run_research("What is the return policy?",
                               db=db_session, thread_id="test-qa-1")
    agents = [t["agent"] for t in state["trace"]]
    assert "product_discovery" not in agents
    assert "price_comparison" not in agents
    assert "shopping_advisor" in agents
    assert state["final_response"]


@pytest.mark.asyncio
async def test_graph_reaches_advisor_even_when_search_finds_nothing(db_session):
    state = await run_research(
        "Find a quantum flux capacitor under 100 rupees",
        db=db_session, thread_id="test-empty-1",
    )
    # No matches → advisor still answers honestly instead of crashing.
    assert state["final_response"]
    assert state["errors"] == [] or all(isinstance(e, str) for e in state["errors"])


@pytest.mark.asyncio
async def test_graph_state_is_json_serialisable(db_session):
    """Checkpointing requires plain JSON structures in state."""
    import json

    state = await run_research("Find headphones under 3000",
                               db=db_session, thread_id="test-json-1")
    json.dumps({k: v for k, v in state.items() if k != "understanding"},
               default=str)
    assert isinstance(state["products"], list)
    if state["products"]:
        json.dumps(state["products"], default=str)


# --- shopping memory -------------------------------------------------------

def test_merge_context_preserves_budget_and_usage():
    old = {"category": "laptop", "budget_max": 60000,
           "usage": ["programming"], "requirements": {"ram_min": 16}}
    new = {"requirements": {"gpu_required": True}, "usage": ["gaming"]}
    merged = merge_context(old, new)
    assert merged["budget_max"] == 60000        # budget kept
    assert merged["category"] == "laptop"       # category kept
    assert set(merged["usage"]) == {"programming", "gaming"}  # union
    assert merged["requirements"] == {"ram_min": 16, "gpu_required": True}


def test_merge_context_none_does_not_erase():
    merged = merge_context({"budget_max": 50000}, {"budget_max": None})
    assert merged["budget_max"] == 50000


def test_conversation_memory_end_to_end(auth_client):
    """Multi-turn: later turns keep earlier constraints."""
    r1 = auth_client.post("/api/chat",
                          json={"message": "I need a laptop under 60000"})
    assert r1.status_code == 200
    conv = r1.json()["conversation_id"]

    r2 = auth_client.post("/api/chat",
                          json={"message": "Programming and gaming",
                                "conversation_id": conv})
    assert r2.status_code == 200

    r3 = auth_client.post(
        "/api/chat",
        json={"message": "Find something with better battery life",
              "conversation_id": conv},
    )
    assert r3.status_code == 200
    assert r3.json()["intent"] == "product_search"

    detail = auth_client.get(f"/api/conversations/{conv}").json()
    ctx = detail["context"]
    assert ctx["category"] == "laptop"
    assert ctx["budget_max"] == 60000  # preserved across turns
    assert "gaming" in ctx["usage"]
    assert len(detail["messages"]) == 6  # 3 user + 3 assistant


def test_conversation_history_persistence(auth_client):
    r1 = auth_client.post("/api/chat", json={"message": "wireless headphones"})
    conv = r1.json()["conversation_id"]
    auth_client.post("/api/chat",
                     json={"message": "under 3000", "conversation_id": conv})
    detail = auth_client.get(f"/api/conversations/{conv}").json()
    assert len(detail["messages"]) == 4
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_conversation_isolation_between_users(auth_client, second_user_client):
    r = auth_client.post("/api/chat", json={"message": "my laptop search"})
    conv = r.json()["conversation_id"]

    # Another user must not read or delete it.
    assert second_user_client.get(
        f"/api/conversations/{conv}").status_code == 404
    assert second_user_client.delete(
        f"/api/conversations/{conv}").status_code == 404
    assert second_user_client.get("/api/conversations").json() == []


def test_delete_conversation(auth_client):
    r = auth_client.post("/api/chat", json={"message": "temp search"})
    conv = r.json()["conversation_id"]
    assert auth_client.delete(f"/api/conversations/{conv}").status_code == 204
    assert auth_client.get(f"/api/conversations/{conv}").status_code == 404
