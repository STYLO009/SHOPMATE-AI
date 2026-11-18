"""Authorized merchant / affiliate API provider.

Reads its configuration from the environment:

    MERCHANT_API_URL   base URL of the merchant search endpoint
    MERCHANT_API_KEY   bearer token (server-side only, never shipped to the UI)

Expected upstream contract (documented for integration partners):

    GET {MERCHANT_API_URL}/search?q=<query>&category=<c>&limit=<n>
    Authorization: Bearer {MERCHANT_API_KEY}
    200 -> {"products": [ {provider_product_id, title, price, currency,
            merchant, brand, category, description, product_url, image_url,
            specifications{}, rating, review_count, availability,
            last_verified_at, reviews[]} ]}

When the environment variables are absent the provider reports
"not_configured" and the registry falls back to the sample dataset (labelled
as sample data in every response). This adapter never invents prices.
"""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from app.core.config import settings
from app.providers.base import ProductProvider, ProviderError, ProviderProduct
from app.utils.validators import is_valid_url

logger = logging.getLogger("shopmate.providers.merchant")


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class MerchantProvider(ProductProvider):
    """Adapter for an authorized merchant or affiliate product feed."""

    name = "merchant_api"
    source_type = "merchant_api"

    @property
    def configured(self) -> bool:
        return bool(settings.merchant_api_url and settings.merchant_api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.merchant_api_key}",
            "Accept": "application/json",
            "User-Agent": "ShopMateAI/1.0",
        }

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        limit: int = 20,
    ) -> list[ProviderProduct]:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", retriable=False)

        params: dict[str, Any] = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        if budget_max is not None:
            params["max_price"] = budget_max
        if budget_min is not None:
            params["min_price"] = budget_min

        url = urljoin(settings.merchant_api_url.rstrip("/") + "/", "search")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                resp = await client.get(url, params=params, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.warning("merchant_search_failed error=%s", exc)
            raise ProviderError(self.name, f"request_failed: {exc}") from exc

        if resp.status_code >= 500:
            raise ProviderError(self.name, f"upstream_{resp.status_code}")
        if resp.status_code == 401 or resp.status_code == 403:
            raise ProviderError(self.name, "unauthorized", retriable=False)
        if resp.status_code != 200:
            raise ProviderError(self.name, f"unexpected_status_{resp.status_code}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise ProviderError(self.name, "invalid_json") from exc

        items = payload.get("products") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ProviderError(self.name, "invalid_payload", retriable=False)

        products = [self._to_product(item) for item in items[:limit]]
        logger.info("merchant_search_ok results=%d took_ms=%d",
                    len(products), int((time.perf_counter() - started) * 1000))
        return products

    async def get_product(self, provider_product_id: str) -> Optional[ProviderProduct]:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", retriable=False)
        url = urljoin(settings.merchant_api_url.rstrip("/") + "/",
                      f"products/{provider_product_id}")
        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                resp = await client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ProviderError(self.name, f"request_failed: {exc}") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise ProviderError(self.name, f"unexpected_status_{resp.status_code}")
        data = resp.json()
        if isinstance(data, dict) and "product" in data:
            data = data["product"]
        return self._to_product(data)

    def _to_product(self, item: dict[str, Any]) -> ProviderProduct:
        # Strict validation: reject records missing essential pricing fields
        # rather than inventing defaults.
        if not item.get("title") or item.get("price") is None:
            raise ProviderError(self.name, "invalid_product_record", retriable=False)
        provider_id = item.get("provider_product_id") or item.get("id")
        try:
            price = float(item["price"])
        except (TypeError, ValueError):
            raise ProviderError(self.name, "invalid_product_price", retriable=False)
        if not provider_id or not math.isfinite(price) or price < 0:
            raise ProviderError(self.name, "invalid_product_record", retriable=False)
        product_url = item.get("product_url")
        image_url = item.get("image_url")
        return ProviderProduct(
            provider_product_id=str(provider_id),
            title=str(item["title"]),
            price=price,
            merchant=str(item.get("merchant") or "Unknown merchant"),
            currency=str(item.get("currency") or "INR"),
            brand=item.get("brand"),
            category=item.get("category"),
            description=item.get("description"),
            product_url=product_url if is_valid_url(product_url) else None,
            image_url=image_url if is_valid_url(image_url) else None,
            specifications=item.get("specifications") or {},
            rating=item.get("rating"),
            review_count=item.get("review_count"),
            availability=item.get("availability") or "unknown",
            source_type="merchant_api",
            source_name=item.get("source_name") or "Authorized merchant API",
            is_sample_data=False,
            last_verified_at=_parse_dt(item.get("last_verified_at")),
            reviews=item.get("reviews") or [],
        )
