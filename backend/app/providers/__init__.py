"""Provider registry: merges results from every configured provider.

- Deduplicates across providers (brand + title + merchant key).
- Never fabricates data: provider failures are reported per-provider in
  `provider_errors` while successful providers still return results.
- Clearly flags when the whole result set comes from sample data.
"""

import logging
import time
from typing import Optional

from app.providers.base import (
    ProductProvider,
    ProviderError,
    ProviderProduct,
    ProviderResult,
)
from app.providers.merchant_provider import MerchantProvider
from app.providers.amazon_creators import AmazonCreatorsProvider
from app.providers.flipkart_affiliate import FlipkartAffiliateProvider
from app.providers.mock_provider import SampleDataProvider
from app.utils.validators import product_dedupe_key

logger = logging.getLogger("shopmate.providers.registry")


class ProviderRegistry:
    def __init__(self, providers: Optional[list[ProductProvider]] = None):
        self.amazon = AmazonCreatorsProvider()
        self.flipkart = FlipkartAffiliateProvider()
        self.merchant = MerchantProvider()
        self.sample = SampleDataProvider()
        # Order matters: authorized data first, sample data as labelled fallback.
        self.providers = providers if providers is not None else [
            self.amazon, self.flipkart, self.merchant, self.sample
        ]

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self.providers]

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        limit: int = 20,
    ) -> ProviderResult:
        started = time.perf_counter()
        merged: dict[str, ProviderProduct] = {}
        errors: list[str] = []
        names: list[str] = []
        sample_only = True
        any_success = False

        for provider in self.providers:
            # Skip the sample fallback when authorized data already succeeded,
            # so sample records never masquerade as live listings.
            if provider.name == "sample_dataset" and any_success:
                continue
            try:
                results = await provider.search(
                    query=query,
                    category=category,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    # Fetch extra so dedupe still fills the requested limit.
                    limit=limit * 2,
                )
            except ProviderError as exc:
                logger.warning("provider_error provider=%s message=%s", exc.provider, exc.message)
                errors.append(f"{provider.name}: {exc.message}")
                continue
            except Exception as exc:  # defensive: one provider must not break search
                logger.exception("provider_crash provider=%s", provider.name)
                errors.append(f"{provider.name}: {type(exc).__name__}")
                continue

            any_success = True
            names.append(provider.name)
            if not provider.source_type == "sample":
                sample_only = False
            for p in results:
                key = p.dedupe_key
                existing = merged.get(key)
                # Keep the freshest verified record when duplicates collide.
                if existing is None or p.last_verified_at > existing.last_verified_at:
                    merged[key] = p

        products = list(merged.values())[:limit]
        elapsed = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            products=products,
            provider_name="+".join(names) if names else "none",
            is_sample_data=sample_only and bool(products),
            error="; ".join(errors) if errors else None,
            took_ms=elapsed,
        )

    async def search_live(
        self,
        query: str,
        category: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        limit: int = 20,
    ) -> ProviderResult:
        """Search connected live providers only; never pad public offers with demo data."""
        started = time.perf_counter()
        merged: dict[str, ProviderProduct] = {}
        errors: list[str] = []
        names: list[str] = []
        for provider in self.providers:
            if provider.source_type == "sample":
                continue
            try:
                results = await provider.search(
                    query=query,
                    category=category,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    limit=limit,
                )
            except ProviderError as exc:
                errors.append(f"{provider.name}: {exc.message}")
                continue
            except Exception as exc:
                logger.exception("provider_crash provider=%s", provider.name)
                errors.append(f"{provider.name}: {type(exc).__name__}")
                continue
            names.append(provider.name)
            for product in results:
                key = product.dedupe_key
                existing = merged.get(key)
                if existing is None or product.last_verified_at > existing.last_verified_at:
                    merged[key] = product
        return ProviderResult(
            products=list(merged.values())[:limit],
            provider_name="+".join(names) if names else "none",
            is_sample_data=False,
            error="; ".join(errors) if errors else None,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def get_product(self, provider_product_id: str) -> Optional[ProviderProduct]:
        """Fetch a product by id, trying each provider in order."""
        for provider in self.providers:
            try:
                result = await provider.get_product(provider_product_id)
            except ProviderError as exc:
                logger.warning("provider_get_error provider=%s message=%s",
                               exc.provider, exc.message)
                continue
            if result is not None:
                return result
        return None

    async def check_price(self, provider_product_id: str) -> Optional[ProviderProduct]:
        """Re-verify a price with the provider that owns the id."""
        for provider in self.providers:
            try:
                result = await provider.check_price(provider_product_id)
            except ProviderError:
                continue
            if result is not None:
                return result
        return None

    def dedupe(self, products: list[ProviderProduct]) -> list[ProviderProduct]:
        seen: dict[str, ProviderProduct] = {}
        for p in products:
            key = product_dedupe_key(p.title, p.brand, p.merchant)
            if key not in seen:
                seen[key] = p
        return list(seen.values())


_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
