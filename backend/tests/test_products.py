"""Product search / filtering / comparison / data-integrity tests."""


def test_search_returns_normalised_products(auth_client):
    resp = auth_client.post("/api/products/search", json={"query": "laptop"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    p = body["products"][0]
    for field in ("id", "title", "price", "currency", "merchant",
                  "source_type", "last_verified_at"):
        assert field in p
    assert p["is_sample_data"] is True  # sample data must be labelled
    assert body["is_sample_data"] is True


def test_search_respects_budget(auth_client):
    resp = auth_client.post(
        "/api/products/search",
        json={"query": "laptop", "category": "laptop", "budget_max": 40000},
    )
    assert resp.status_code == 200
    for p in resp.json()["products"]:
        assert p["price"] <= 40000


def test_search_category_filter(auth_client):
    resp = auth_client.post(
        "/api/products/search",
        json={"query": "wireless headphones", "category": "headphones"},
    )
    assert resp.status_code == 200
    for p in resp.json()["products"]:
        assert p["category"] == "headphones"


def test_search_rejects_inverted_budget(auth_client):
    resp = auth_client.post(
        "/api/products/search",
        json={"query": "laptop", "budget_min": 90000, "budget_max": 10000},
    )
    assert resp.status_code == 422


def test_search_requires_query(auth_client):
    assert auth_client.post("/api/products/search", json={"query": ""}).status_code == 422


def test_get_product_by_provider_id(auth_client):
    resp = auth_client.post("/api/products/search", json={"query": "laptop"})
    provider_id = resp.json()["products"][0]["provider_product_id"]
    detail = auth_client.get(f"/api/products/{provider_id}")
    assert detail.status_code == 200
    assert detail.json()["provider_product_id"] == provider_id


def test_get_product_404(auth_client):
    assert auth_client.get("/api/products/SMP-XXX-999").status_code == 404


def test_compare_two_products(auth_client):
    resp = auth_client.post(
        "/api/products/compare",
        json={"product_ids": ["SMP-PHN-001", "SMP-PHN-002"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["products"]) == 2
    assert body["price_difference"] is not None
    assert body["cheapest_product_id"]
    assert body["best_value_id"]
    # Differences must contain only specs that actually differ.
    for d in body["spec_differences"]:
        assert len(set(d["values"].values())) > 1


def test_compare_needs_two_products(auth_client):
    resp = auth_client.post("/api/products/compare",
                            json={"product_ids": ["SMP-PHN-001"]})
    assert resp.status_code == 422


def test_compare_unknown_products_404(auth_client):
    resp = auth_client.post(
        "/api/products/compare",
        json={"product_ids": ["nope-1", "nope-2"]},
    )
    assert resp.status_code == 404


def test_products_never_missing_price(auth_client):
    """Data integrity: every listing carries a real price + verification time."""
    resp = auth_client.post("/api/products/search", json={"query": "laptop"})
    assert resp.status_code == 200
    assert resp.json()["products"], "expected listings"
    for p in resp.json()["products"]:
        assert p["price"] >= 0
        assert p["last_verified_at"]
        assert p["source_type"] in ("sample", "merchant_api", "affiliate_feed",
                                    "user_url", "public_dataset")


def test_product_urls_are_valid(auth_client):
    resp = auth_client.post("/api/products/search", json={"query": "laptop"})
    for p in resp.json()["products"]:
        if p["product_url"]:
            assert p["product_url"].startswith(("http://", "https://"))
