"""Agent 5 — Specification Analysis Agent.

Compares category-specific specifications across candidate products,
identifies performance differences and translates technical jargon into
plain language. Missing specs are reported, not guessed.
"""

import logging
from typing import Any, Optional

from app.utils.ranking import spec_key_weights

logger = logging.getLogger("shopmate.agents.spec")

# Plain-language explanations for common spec differences.
_PLAIN = {
    "ram_gb": "RAM affects how many apps/tabs you can run at once — more is better "
              "for multitasking and dev tools.",
    "storage_gb": "Storage capacity determines how much you can install and keep offline.",
    "storage_type": "NVMe/SSD storage makes boot and file transfers noticeably faster.",
    "gpu": "The graphics chip drives gaming frame rates and GPU-accelerated workloads.",
    "cpu": "The processor determines raw compute speed for compiling, rendering and apps.",
    "battery_hours": "Battery life decides how long you can work unplugged.",
    "battery_days": "Battery endurance between charges for daily wearables.",
    "refresh_rate_hz": "A higher refresh rate makes scrolling and motion look smoother.",
    "camera_mp": "More megapixels (with a good sensor) capture finer detail.",
    "charging_w": "Higher wattage charging refills the battery faster.",
    "anc": "Active noise cancelling reduces ambient noise for focused listening.",
    "driver_mm": "Larger drivers can move more air — often (not always) richer bass.",
    "screen_size_in": "Screen size trades portability against immersion.",
    "weight_kg": "Lighter devices are easier to carry all day.",
    "water_resistance": "Water resistance protects against rain and sweat.",
    "gps": "Built-in GPS tracks outdoor activity without your phone.",
    "multipoint": "Multipoint Bluetooth connects to two devices simultaneously.",
    "storage_type": "Storage technology affects app load times.",
}


class SpecificationAnalysisAgent:
    name = "specification_analysis"

    async def run(
        self,
        products: list[dict[str, Any]],
        requirements: Optional[dict[str, Any]] = None,
        category: Optional[str] = None,
    ) -> dict[str, Any]:
        if not products:
            return {
                "spec_analysis": {
                    "summary": "No products available to analyse.",
                    "differences": [],
                    "tradeoffs": [],
                    "missing": [],
                }
            }

        cat = category or products[0].get("category")
        weights = spec_key_weights(cat)
        requirements = requirements or {}

        # Union of spec keys with their importance for this category.
        key_order: list[str] = []
        for p in products:
            for k in (p.get("specifications") or {}):
                if k not in key_order:
                    key_order.append(k)

        differences: list[dict[str, Any]] = []
        missing: list[str] = []
        tradeoffs: list[str] = []

        for key in key_order:
            values = {
                p["product_id"]: (p.get("specifications") or {}).get(key)
                for p in products
            }
            published = {pid: v for pid, v in values.items() if v is not None}
            if len(published) < len(products):
                missing.append(key)
            if len(set(map(_hashable, values.values()))) <= 1:
                continue  # identical (or all missing) — not a meaningful difference

            importance = weights.get(key, 0.3)
            explanation = _PLAIN.get(key)
            differences.append({
                "spec": key,
                "values": {pid: _fmt(v) for pid, v in values.items()},
                "importance": importance,
                "explanation": explanation,
                "required": key in requirements or _req_key_for(key) in requirements,
            })

        # Sort by importance so the UI shows meaningful diffs first.
        differences.sort(key=lambda d: -d["importance"])

        # Trade-off narrative (data-driven, no fabrication).
        if len(products) >= 2:
            best_ram = max(products,
                           key=lambda p: _num((p.get("specifications") or {}).get("ram_gb")))
            cheapest = min(products, key=lambda p: p.get("price", 0))
            if best_ram["product_id"] != cheapest["product_id"]:
                tradeoffs.append(
                    f"{best_ram['title']} leads on RAM/performance while "
                    f"{cheapest['title']} is the cheapest option."
                )

        summary = (
            f"Compared {len(key_order)} specification fields across "
            f"{len(products)} product(s); {len(differences)} differ meaningfully."
            + (f" {len(missing)} field(s) are not published for every product."
               if missing else "")
        )

        return {
            "spec_analysis": {
                "summary": summary,
                "differences": differences[:12],
                "tradeoffs": tradeoffs,
                "missing": missing,
                "category": cat,
            }
        }


def _req_key_for(spec_key: str) -> str:
    return {
        "ram_gb": "ram_min", "storage_gb": "storage_min",
        "battery_hours": "battery_min_hours", "camera_mp": "camera_min_mp",
    }.get(spec_key, spec_key)


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return -1


def _hashable(v: Any) -> Any:
    return v if isinstance(v, (str, int, float, bool)) or v is None else str(v)


def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)
