"""Watchlist, saved products, provider-failure and system tests."""

from datetime import datetime, timezone

import pytest

from app.providers import ProviderRegistry
from app.providers.base import ProductProvider, ProviderError


# --- watchlist / saved products -------------------------------------------

def _first_product_id(client) -> str:
    resp = client.post("/api/products/search", json={"query": "laptop"})
    return resp.json()["products"][0]["id"]


def test_watchlist_add_list_remove(auth_client):
    pid = _first_product_id(auth_client)
    r = auth_client.post("/api/watchlist",
                         json={"product_id": pid, "target_price": 50000})
    assert r.status_code == 201
    entry = r.json()
    assert entry["target_price"] == 50000
    assert entry["product"]["price"] > 0

    listed = auth_client.get("/api/watchlist").json()
    assert len(listed) == 1

    assert auth_client.delete(f"/api/watchlist/{pid}").status_code == 204
    assert auth_client.get("/api/watchlist").json() == []


def test_watchlist_unknown_product_404(auth_client):
    resp = auth_client.post("/api/watchlist", json={"product_id": "missing"})
    assert resp.status_code == 404


def test_watchlist_refresh_records_real_checks(auth_client):
    pid = _first_product_id(auth_client)
    auth_client.post("/api/watchlist", json={"product_id": pid})
    r = auth_client.post("/api/watchlist/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] >= 1
    assert body["results"][0]["status"] in ("ok", "unavailable")
    entry = auth_client.get("/api/watchlist").json()[0]
    assert entry["check_count"] >= 1
    assert entry["last_checked_at"] is not None


def test_saved_products_add_list_remove(auth_client):
    pid = _first_product_id(auth_client)
    r = auth_client.post("/api/watchlist/saved", json={"product_id": pid})
    assert r.status_code == 201
    saved = auth_client.get("/api/watchlist/saved").json()
    assert len(saved) == 1
    assert saved[0]["product"]["product_id"] == pid
    assert auth_client.delete(
        f"/api/watchlist/saved/{pid}").status_code == 204


def test_saved_products_isolated_between_users(auth_client, second_user_client):
    pid = _first_product_id(auth_client)
    auth_client.post("/api/watchlist/saved", json={"product_id": pid})
    # Second user has their own (empty) list.
    assert second_user_client.get("/api/watchlist/saved").json() == []
    # And cannot remove the first user's save.
    resp = second_user_client.delete(f"/api/watchlist/saved/{pid}")
    assert resp.status_code == 404
    # First user's save is untouched.
    assert len(auth_client.get("/api/watchlist/saved").json()) == 1


def test_watchlist_isolated_between_users(auth_client, second_user_client):
    pid = _first_product_id(auth_client)
    auth_client.post("/api/watchlist", json={"product_id": pid})
    assert second_user_client.get("/api/watchlist").json() == []
    assert second_user_client.delete(f"/api/watchlist/{pid}").status_code == 404


# --- provider failure handling ---------------------------------------------

class _FailingProvider(ProductProvider):
    name = "failing"
    source_type = "merchant_api"

    async def search(self, query, category=None, budget_min=None,
                     budget_max=None, limit=20):
        raise ProviderError(self.name, "upstream_500")


class _ExplodingProvider(ProductProvider):
    name = "exploding"
    source_type = "affiliate_feed"

    async def search(self, query, category=None, budget_min=None,
                     budget_max=None, limit=20):
        raise RuntimeError("unexpected boom")


@pytest.mark.asyncio
async def test_registry_degrades_when_providers_fail(auth_client):
    """One broken provider must not break search — errors are reported."""
    from app.providers.mock_provider import SampleDataProvider

    registry = ProviderRegistry(
        providers=[_FailingProvider(), _ExplodingProvider(), SampleDataProvider()]
    )
    result = await registry.search("laptop", limit=5)
    assert result.products, "sample fallback should still return results"
    assert result.error and "failing" in result.error
    assert "exploding" in result.error


@pytest.mark.asyncio
async def test_registry_merchant_not_configured_is_reported(auth_client):
    from app.providers.mock_provider import SampleDataProvider

    registry = ProviderRegistry(
        providers=[ProviderRegistry().merchant, SampleDataProvider()]
    )
    result = await registry.search("laptop", limit=5)
    assert "merchant_api: not_configured" in (result.error or "")
    assert result.is_sample_data is True  # clearly labelled


@pytest.mark.asyncio
async def test_search_endpoint_reports_provider_errors(auth_client):
    resp = auth_client.post("/api/products/search", json={"query": "laptop"})
    assert resp.status_code == 200
    body = resp.json()
    # merchant not configured in tests → surfaced, not hidden
    assert body["provider_errors"]
    assert body["is_sample_data"] is True


# --- system ----------------------------------------------------------------

def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["checks"]["database"] == "ok"
    assert "sample_dataset" in body["checks"]["providers"]


def test_openapi_available(client):
    assert client.get("/openapi.json").status_code == 200


def test_rate_limit_headers_present(client):
    resp = client.get("/api/health")
    assert "X-Request-ID" in resp.headers
    assert "X-Response-Time-Ms" in resp.headers
