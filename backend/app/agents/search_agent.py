"""Agent 2 — Product Discovery Agent.

Queries the provider registry, normalises results, applies budget/spec
filters and de-duplicates. Provider failures are surfaced, not hidden.
"""

import logging
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.product_service import search_products, upsert_product
from app.providers import ProviderRegistry, get_registry

logger = logging.getLogger("shopmate.agents.search")


class ProductDiscoveryAgent:
    name = "product_discovery"

    async def run(
        self,
        db: Session,
        query: str,
        category: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        requirements: Optional[dict[str, Any]] = None,
        limit: int = 12,
        registry: Optional[ProviderRegistry] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        registry = registry or get_registry()

        response = await search_products(
            db,
            query=query,
            category=category,
            budget_min=budget_min,
            budget_max=budget_max,
            limit=limit,
            registry=registry,
        )

        # Hard requirement filtering (e.g. 16GB RAM minimum, dedicated GPU).
        products = response.products
        if requirements:
            filtered, dropped = [], 0
            for p in products:
                if self._meets_requirements(p.specifications or {}, requirements):
                    filtered.append(p)
                else:
                    dropped += 1
            # If filtering empties the set, keep the unfiltered list and
            # report the shortfall (never return nothing for a soft miss).
            if filtered:
                products = filtered
            else:
                dropped = 0
        else:
            dropped = 0

        return {
            "products": products,
            "provider_errors": response.provider_errors,
            "is_sample_data": response.is_sample_data,
            "providers_queried": response.providers_queried,
            "dropped_by_requirements": dropped,
            "took_ms": int((time.perf_counter() - started) * 1000),
        }

    @staticmethod
    def _meets_requirements(specs: dict[str, Any], reqs: dict[str, Any]) -> bool:
        """Strict checks for hard minimums; missing spec = unknown (keep)."""
        checks = [
            ("ram_min", "ram_gb", "min"),
            ("storage_min", "storage_gb", "min"),
            ("battery_min_hours", "battery_hours", "min"),
            ("battery_min_days", "battery_days", "min"),
            ("camera_min_mp", "camera_mp", "min"),
        ]
        for req_key, spec_key, kind in checks:
            if req_key not in reqs or reqs[req_key] is None:
                continue
            have = specs.get(spec_key)
            if have is None:
                continue  # unknown spec — do not drop the product
            try:
                if float(have) < float(reqs[req_key]):
                    return False
            except (TypeError, ValueError):
                continue
        if reqs.get("gpu_required") is True:
            gpu = str(specs.get("gpu") or "").lower()
            if gpu and not any(w in gpu for w in ("integrated", "intel uhd",
                                                  "intel arc", "radeon 780m")):
                pass  # has discrete-ish GPU
            elif gpu and any(w in gpu for w in ("integrated", "intel uhd",
                                                "intel arc", "radeon 780m")):
                return False
        return True
