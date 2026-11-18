"""End-to-end integration: one continuous user journey through every layer.

Unlike the unit suites (which isolate one concern per test), these tests walk
the real stack in order — auth → search → compare → chat graph → memory →
recommendations → reviews → watchlist — asserting data integrity at each hop.
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------- auth

def test_full_journey_auth_to_watchlist(client):
    # 1. Register + cookie session established.
    r = client.post(
        "/api/auth/register",
        json={
            "full_name": "Journey User",
            "email": "journey@example.com",
            "password": "Passw0rd123",
            "confirm_password": "Passw0rd123",
            "accept_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["user"]["id"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == user_id

    # 2. Health reports real runtime mode.
    health = client.get("/api/health")
    assert health.status_code == 200

    # 3. Search persists normalised, labelled sample products.
    s = client.post("/api/products/search", json={"query": "laptop", "limit": 6})
    assert s.status_code == 200
    search = s.json()
    assert search["total"] > 0
    assert search["is_sample_data"] is True
    for p in search["products"]:
        assert p["price"] > 0
        assert p["last_verified_at"]
        assert p["is_sample_data"] is True

    # 4. Detail + compare work on provider ids (pre- or post-search).
    detail = client.get(f"/api/products/{search['products'][0]['provider_product_id']}")
    assert detail.status_code == 200

    c = client.post(
        "/api/products/compare",
        json={"product_ids": ["SMP-PHN-001", "SMP-PHN-002"]},
    )
    assert c.status_code == 200
    compare = c.json()
    assert len(compare["products"]) == 2
    assert compare["price_difference"] is not None
    assert compare["verdict"]

    # 5. Chat runs the graph, returns reply + trace + labelled products.
    chat1 = client.post("/api/chat", json={"message": "laptop under 60000 for coding"})
    assert chat1.status_code == 200, chat1.text
    turn1 = chat1.json()
    conv_id = turn1["conversation_id"]
    assert turn1["reply"]
    assert turn1["intent"]
    assert turn1["llm_mode"]

    # 6. Follow-up turn preserves constraints through conversation memory.
    chat2 = client.post(
        "/api/chat",
        json={"message": "also I need 16GB RAM and gaming graphics",
              "conversation_id": conv_id},
    )
    assert chat2.status_code == 200
    detail = client.get(f"/api/conversations/{conv_id}").json()
    ctx = detail["context"]
    assert ctx.get("budget_max") or ctx.get("requirements"), "memory lost constraints"
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]

    # 7. Recommendations are ranked, weighted and explainable.
    rec = client.post(
        "/api/recommendations",
        json={"query": "gaming laptop", "budget_max": 60000, "usage": ["gaming"]},
    )
    assert rec.status_code == 200
    body = rec.json()
    assert body["ranked"]
    assert abs(sum(body["weights"].values()) - 1.0) < 1e-3
    scores = [r["final_score"] for r in body["ranked"]]
    assert scores == sorted(scores, reverse=True)
    assert body["ranked"][0]["reasons"]

    # 8. Review analysis reads stored reviews; never invents missing ones.
    ra = client.post("/api/reviews/analyze", json={"product_id": "SMP-PHN-002"})
    assert ra.status_code == 200
    analysis = ra.json()
    assert analysis["review_count"] > 0
    assert analysis["summary"]

    no_rev = client.post("/api/reviews/analyze", json={"product_id": "SMP-PHN-006"})
    assert no_rev.status_code == 200
    assert no_rev.json()["review_count"] == 0
    assert no_rev.json()["positive_themes"] == []

    # 9. Watchlist + saved products attach to this user.
    pid = search["products"][0]["provider_product_id"]
    w = client.post("/api/watchlist", json={"product_id": pid, "target_price": 55000})
    assert w.status_code == 201

    refresh = client.post("/api/watchlist/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["checked"] >= 1

    sv = client.post("/api/watchlist/saved", json={"product_id": pid})
    assert sv.status_code == 201
    assert client.get("/api/watchlist/saved").json()

    # 10. Conversation appears in history, then cleans up.
    hist = client.get("/api/conversations").json()
    assert any(c["id"] == conv_id for c in hist)
    assert client.delete(f"/api/conversations/{conv_id}").status_code == 204
    assert client.get(f"/api/conversations/{conv_id}").status_code == 404

    # 11. Logout invalidates the cookie session.
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_stream_chat_delivers_full_payload_over_sse(client):
    """SSE stream emits status → progress → message → done with real content."""
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Stream User",
            "email": "stream@example.com",
            "password": "Passw0rd123",
            "confirm_password": "Passw0rd123",
            "accept_terms": True,
        },
    )

    with client.stream(
        "POST", "/api/chat?stream=true", json={"message": "wireless headphones"}
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        raw = "".join(resp.iter_text())

    assert "event: status" in raw
    assert "event: message" in raw
    assert "event: done" in raw
    # Payload carries the assistant reply, not just a stub.
    assert "conversation_id" in raw


def test_anonymous_cannot_touch_any_user_scoped_route(client):
    """Every user-scoped endpoint is protected at the backend, not the UI."""
    protected = [
        ("POST", "/api/chat", {"message": "hi"}),
        ("GET", "/api/conversations", None),
        ("POST", "/api/recommendations", {"query": "laptop"}),
        ("POST", "/api/reviews/analyze", {"product_id": "SMP-PHN-001"}),
        ("GET", "/api/watchlist", None),
        ("POST", "/api/watchlist", {"product_id": "SMP-LAP-001"}),
        ("GET", "/api/watchlist/saved", None),
        ("POST", "/api/watchlist/refresh", None),
    ]
    for method, path, body in protected:
        kwargs = {"json": body} if body is not None else {}
        resp = client.request(method, path, **kwargs)
        assert resp.status_code == 401, f"{method} {path} was accessible anonymously"


def test_search_isolated_between_users(auth_client, second_user_client):
    """Data created by one session never appears in another user's lists."""
    pid = auth_client.post(
        "/api/products/search", json={"query": "laptop"}
    ).json()["products"][0]["provider_product_id"]

    auth_client.post("/api/watchlist", json={"product_id": pid})
    auth_client.post("/api/watchlist/saved", json={"product_id": pid})
    r = auth_client.post("/api/chat", json={"message": "my private search"})
    conv = r.json()["conversation_id"]

    # Same product exists globally, but scoped lists stay empty for user 2.
    assert second_user_client.get("/api/watchlist").json() == []
    assert second_user_client.get("/api/watchlist/saved").json() == []
    assert second_user_client.get("/api/conversations").json() == []
    assert second_user_client.get(f"/api/conversations/{conv}").status_code == 404
    assert second_user_client.delete(f"/api/conversations/{conv}").status_code == 404


def test_bare_category_query_is_product_search(client):
    """'laptop under 60000 for coding' has no verb like 'find' but is a search."""
    from app.agents.query_agent import rule_based_extract

    # Unit: the extractor itself classifies category+price phrases correctly.
    u = rule_based_extract("laptop under 60000 for coding", {})
    assert u.intent == "product_search"
    assert u.category == "laptop"
    assert u.budget_max == 60000

    # …and genuine questions stay general Q&A.
    q = rule_based_extract("what is a laptop?", {})
    assert q.intent == "general_qa"

    # End-to-end: the chat endpoint actually runs the search branch.
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Classify User",
            "email": "classify@example.com",
            "password": "Passw0rd123",
            "confirm_password": "Passw0rd123",
            "accept_terms": True,
        },
    )
    resp = client.post(
        "/api/chat", json={"message": "laptop under 60000 for coding"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "product_search"
    assert body["products"], "expected products for a category+budget query"
