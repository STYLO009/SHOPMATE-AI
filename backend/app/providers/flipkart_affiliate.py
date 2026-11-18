"""Flipkart's documented affiliate product and active-offer APIs."""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.providers.base import ProductProvider, ProviderError, ProviderProduct
from app.utils.validators import is_valid_url

logger = logging.getLogger("shopmate.providers.flipkart")
BASE_URL = "https://affiliate-api.flipkart.net/affiliate"


def _amount(value: Any) -> Optional[float]:
    if isinstance(value, dict):
        value = value.get("amount")
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError):
        return None


class FlipkartAffiliateProvider(ProductProvider):
    name = "flipkart_affiliate"
    source_type = "affiliate_feed"

    def __init__(self) -> None:
        self._offer_cache: dict[bool, tuple[float, list[dict[str, Any]]]] = {}

    @property
    def configured(self) -> bool:
        return settings.flipkart_affiliate_configured

    def _headers(self) -> dict[str, str]:
        return {
            "Fk-Affiliate-Id": settings.flipkart_affiliate_id,
            "Fk-Affiliate-Token": settings.flipkart_affiliate_token,
            "Accept": "application/json",
            "User-Agent": "ShopMateAI/1.0",
        }

    async def _get_json(self, url: str, params: Optional[dict[str, Any]] = None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                response = await client.get(url, params=params, headers=self._headers())
            if response.status_code in (401, 403):
                raise ProviderError(self.name, "affiliate_credentials_rejected", retriable=False)
            if response.status_code >= 500 or response.status_code == 429:
                raise ProviderError(self.name, f"upstream_{response.status_code}")
            response.raise_for_status()
            return response.json()
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(self.name, f"request_failed: {type(exc).__name__}") from exc

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
        if not query.strip():
            return []
        payload = await self._get_json(
            f"{BASE_URL}/1.0/search.json",
            {"query": query, "resultCount": min(max(limit, 1), 10)},
        )
        rows = payload.get("productInfoList", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            raise ProviderError(self.name, "invalid_payload", retriable=False)
        products: list[ProviderProduct] = []
        for row in rows:
            try:
                product = self._to_product(row)
            except (ProviderError, TypeError, ValueError):
                logger.warning("flipkart_invalid_product_skipped")
                continue
            if category and product.category and category.lower() not in product.category.lower():
                continue
            if budget_min is not None and product.price < budget_min:
                continue
            if budget_max is not None and product.price > budget_max:
                continue
            products.append(product)
        return products[:limit]

    async def get_product(self, provider_product_id: str) -> Optional[ProviderProduct]:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", retriable=False)
        payload = await self._get_json(
            f"{BASE_URL}/1.0/product.json", {"id": provider_product_id}
        )
        rows = payload.get("productInfoList", []) if isinstance(payload, dict) else []
        if not rows and isinstance(payload, dict) and payload.get("productBaseInfoV1"):
            rows = [payload]
        for row in rows if isinstance(rows, list) else []:
            try:
                product = self._to_product(row)
            except (ProviderError, TypeError, ValueError):
                continue
            if product.provider_product_id == provider_product_id:
                return product
        return None

    async def featured_offers(self, *, deals_of_day: bool = True) -> list[dict[str, Any]]:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", retriable=False)
        cached = self._offer_cache.get(deals_of_day)
        if cached and time.monotonic() < cached[0]:
            return list(cached[1])
        path = "offers/v1/dotd/json" if deals_of_day else "offers/v1/all/json"
        payload = await self._get_json(f"{BASE_URL}/{path}")
        key = "dotdList" if deals_of_day else "allOffersList"
        rows = payload.get(key, []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            raise ProviderError(self.name, "invalid_offer_payload", retriable=False)
        now_ms = int(time.time() * 1000)
        items = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("title") or not is_valid_url(row.get("url")):
                continue
            end_ms = row.get("endTime")
            try:
                if end_ms is not None and int(end_ms) < now_ms:
                    continue
            except (TypeError, ValueError):
                pass
            start_ms = row.get("startTime")
            try:
                if start_ms is not None and int(start_ms) > now_ms:
                    continue
            except (TypeError, ValueError):
                pass
            images = row.get("imageUrls") or []
            image = next((i.get("url") for i in images if i.get("resolutionType") == "high"), None)
            if not image:
                image = next((i.get("url") for i in images if i.get("url")), None)
            items.append({
                "id": f"flipkart-offer-{len(items) + 1}",
                "merchant": "Flipkart",
                "title": str(row["title"]),
                "description": row.get("description"),
                "category": row.get("category"),
                "url": row["url"],
                "image_url": image if is_valid_url(image) else None,
                "availability": row.get("availability", "unknown"),
                "start_at": self._offer_time(row.get("startTime")),
                "expires_at": self._offer_time(row.get("endTime")),
                "last_verified_at": datetime.now(timezone.utc),
                "source_type": "affiliate_feed",
                "is_sample_data": False,
            })
        self._offer_cache[deals_of_day] = (time.monotonic() + 300, items)
        return items

    @staticmethod
    def _offer_time(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        try:
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            if isinstance(value, str):
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            return None

    def _to_product(self, row: dict[str, Any]) -> ProviderProduct:
        base = row.get("productBaseInfoV1") or row.get("productBaseInfoV2") or row
        if not isinstance(base, dict):
            raise ProviderError(self.name, "invalid_product_record", retriable=False)
        identifier = base.get("productId") or (base.get("productIdentifier") or {}).get("productId")
        price = _amount(base.get("flipkartSpecialPrice") or base.get("sellingPrice") or base.get("flipkartSellingPrice"))
        if price is None:
            raise ProviderError(self.name, "product_price_unavailable", retriable=False)
        images = base.get("imageUrls") or {}
        image = images.get("400x400") or images.get("200x200") or images.get("unknown")
        category = base.get("category") or base.get("categoryPath")
        if isinstance(category, list):
            category = " > ".join(str(x) for x in category)
        extras = base.get("offers") or []
        offer_text = "; ".join(str(x.get("description") or x.get("title")) for x in extras if isinstance(x, dict))
        original_price = _amount(base.get("maximumRetailPrice") or base.get("mrp"))
        discount = base.get("discountPercentage")
        try:
            discount = float(discount) if discount is not None else None
        except (TypeError, ValueError):
            discount = None
        available = base.get("isAvailable")
        in_stock = base.get("inStock")
        availability = "in_stock" if available is True or in_stock is True else "out_of_stock" if available is False or in_stock is False else "unknown"
        price_record = base.get("flipkartSpecialPrice") or base.get("sellingPrice") or {}
        currency = price_record.get("currency") if isinstance(price_record, dict) else None
        if not identifier or not base.get("title"):
            raise ProviderError(self.name, "invalid_product_record", retriable=False)
        return ProviderProduct(
            provider_product_id=str(identifier),
            title=str(base["title"]),
            price=price,
            merchant="Flipkart",
            currency=str(currency or "INR"),
            brand=base.get("productBrand"),
            category=str(category) if category else None,
            description=base.get("productDescription"),
            product_url=base.get("productUrl") if is_valid_url(base.get("productUrl")) else None,
            image_url=image if is_valid_url(image) else None,
            specifications={"list_price": original_price, "discount_percentage": discount, "offer_text": offer_text},
            availability=availability,
            source_type=self.source_type,
            source_name="Flipkart Affiliate API",
            is_sample_data=False,
            last_verified_at=datetime.now(timezone.utc),
        )
