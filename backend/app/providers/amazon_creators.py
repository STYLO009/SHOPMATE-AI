"""Amazon Creators API adapter for the Amazon.in marketplace."""

import asyncio
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.providers.base import ProductProvider, ProviderError, ProviderProduct
from app.utils.validators import is_valid_url

logger = logging.getLogger("shopmate.providers.amazon")
CREATORS_BASE = "https://creatorsapi.amazon"
TOKEN_ENDPOINTS = {
    "3.1": "https://api.amazon.com/auth/o2/token",
    "3.2": "https://api.amazon.co.uk/auth/o2/token",
    "3.3": "https://api.amazon.co.jp/auth/o2/token",
}
OFFER_RESOURCES = [
    "images.primary.medium",
    "itemInfo.title",
    "itemInfo.byLineInfo",
    "itemInfo.features",
    "offersV2.listings.price",
    "offersV2.listings.availability",
    "offersV2.listings.dealDetails",
    "offersV2.listings.merchantInfo",
    "offersV2.listings.isBuyBoxWinner",
]


def _path(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _money(obj: Any) -> tuple[Optional[float], str]:
    if not isinstance(obj, dict):
        return None, "INR"
    try:
        amount = float(obj.get("amount"))
        if not math.isfinite(amount) or amount < 0:
            return None, "INR"
        return amount, str(obj.get("currency") or "INR")
    except (TypeError, ValueError):
        return None, "INR"


class AmazonCreatorsProvider(ProductProvider):
    name = "amazon_creators"
    source_type = "affiliate_feed"

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._results: dict[tuple[str, str, int], tuple[float, list[ProviderProduct]]] = {}

    @property
    def configured(self) -> bool:
        return settings.amazon_creators_configured

    async def _access_token(self) -> str:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", retriable=False)
        if settings.amazon_creators_credential_version not in TOKEN_ENDPOINTS:
            raise ProviderError(self.name, "unsupported_credential_version", retriable=False)
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        async with self._token_lock:
            if self._token and time.monotonic() < self._token_expires_at:
                return self._token
            body = {
                "grant_type": "client_credentials",
                "client_id": settings.amazon_creators_client_id,
                "client_secret": settings.amazon_creators_client_secret,
                "scope": "creatorsapi::default",
            }
            try:
                async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                    response = await client.post(
                        TOKEN_ENDPOINTS[settings.amazon_creators_credential_version], json=body
                    )
                response.raise_for_status()
                payload = response.json()
                token = payload.get("access_token")
                expires = int(payload.get("expires_in", 3600))
                if not token:
                    raise ProviderError(self.name, "token_missing", retriable=False)
            except ProviderError:
                raise
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise ProviderError(self.name, f"token_request_failed: {type(exc).__name__}") from exc
            self._token = str(token)
            self._token_expires_at = time.monotonic() + max(expires - 60, 60)
            return self._token

    async def _catalog_request(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = await self._access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-marketplace": settings.amazon_marketplace,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                response = await client.post(
                    f"{CREATORS_BASE}/catalog/v1/{operation}", headers=headers, json=payload
                )
            if response.status_code in (401, 403):
                self._token = None
                if response.status_code == 403:
                    raise ProviderError(self.name, "access_denied_check_associate_eligibility", retriable=False)
                raise ProviderError(self.name, "invalid_or_expired_token")
            if response.status_code >= 500 or response.status_code == 429:
                raise ProviderError(self.name, f"upstream_{response.status_code}")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ProviderError(self.name, "invalid_payload", retriable=False)
            return data
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(self.name, f"catalog_request_failed: {type(exc).__name__}") from exc

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
        query = query.strip()
        if not query:
            return []
        cache_key = (query.lower(), settings.amazon_marketplace, min(max(limit, 1), 10))
        cached = self._results.get(cache_key)
        if cached and time.monotonic() < cached[0]:
            records = list(cached[1])
        else:
            payload = await self._catalog_request("searchItems", {
                "keywords": query,
                "partnerTag": settings.amazon_associate_tag,
                "marketplace": settings.amazon_marketplace,
                "itemCount": min(max(limit, 1), 10),
                "resources": OFFER_RESOURCES,
            })
            rows = _path(payload, "searchResult", "items") or []
            if not isinstance(rows, list):
                raise ProviderError(self.name, "invalid_search_payload", retriable=False)
            records = []
            for row in rows:
                try:
                    product = self._to_product(row)
                except (ProviderError, TypeError, ValueError):
                    logger.warning("amazon_invalid_product_skipped")
                    continue
                records.append(product)
            # Amazon's volatile offer data must not be cached beyond one hour.
            self._results[cache_key] = (time.monotonic() + 3500, records)
        return [p for p in records if
                (budget_min is None or p.price >= budget_min)
                and (budget_max is None or p.price <= budget_max)][:limit]

    async def get_product(self, provider_product_id: str) -> Optional[ProviderProduct]:
        if not self.configured:
            raise ProviderError(self.name, "not_configured", retriable=False)
        payload = await self._catalog_request("getItems", {
            "itemIds": [provider_product_id],
            "itemIdType": "ASIN",
            "partnerTag": settings.amazon_associate_tag,
            "marketplace": settings.amazon_marketplace,
            "resources": OFFER_RESOURCES,
        })
        rows = _path(payload, "itemsResult", "items") or []
        for row in rows if isinstance(rows, list) else []:
            try:
                return self._to_product(row)
            except (ProviderError, TypeError, ValueError):
                continue
        return None

    def _to_product(self, row: dict[str, Any]) -> ProviderProduct:
        asin = row.get("asin")
        title = _path(row, "itemInfo", "title", "displayValue")
        detail_url = row.get("detailPageURL")
        listings = _path(row, "offersV2", "listings") or []
        if not isinstance(listings, list):
            listings = []
        listing = next((x for x in listings if x.get("isBuyBoxWinner")), None)
        if listing is None and listings:
            listing = listings[0]
        price_obj = _path(listing, "price", "money")
        price, currency = _money(price_obj)
        if not asin or not title or price is None:
            raise ProviderError(self.name, "offer_price_unavailable", retriable=False)
        savings_base, _ = _money(_path(listing, "price", "savingBasis", "money"))
        discount = _path(listing, "price", "savings", "percentage")
        try:
            discount = float(discount) if discount is not None else None
        except (TypeError, ValueError):
            discount = None
        features = _path(row, "itemInfo", "features", "displayValues") or []
        merchant = _path(listing, "merchantInfo", "name") or "Amazon.in"
        image = _path(row, "images", "primary", "medium", "url") or _path(row, "images", "primary", "large", "url")
        availability = _path(listing, "availability", "type") or "unknown"
        deal_details = listing.get("dealDetails") if listing else None
        expires = deal_details.get("endTime") if isinstance(deal_details, dict) else None
        try:
            expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00")) if expires else None
        except (ValueError, AttributeError):
            expires_at = None
        specifications: dict[str, Any] = {
            "list_price": savings_base,
            "discount_percentage": discount,
            "offer_text": (deal_details or {}).get("badge") if isinstance(deal_details, dict) else None,
            "offer_expires_at": expires_at.isoformat() if expires_at else None,
        }
        return ProviderProduct(
            provider_product_id=str(asin),
            title=str(title),
            price=price,
            merchant=str(merchant),
            currency=currency,
            brand=_path(row, "itemInfo", "byLineInfo", "brand", "displayValue"),
            description=" ".join(str(x) for x in features[:5]) if isinstance(features, list) else None,
            product_url=detail_url if is_valid_url(detail_url) else None,
            image_url=image if is_valid_url(image) else None,
            specifications=specifications,
            availability=str(availability).lower(),
            source_type=self.source_type,
            source_name="Amazon Creators API",
            is_sample_data=False,
            last_verified_at=datetime.now(timezone.utc),
        )
