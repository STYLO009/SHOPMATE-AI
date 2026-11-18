"""Agent 7 — Shopping Advisor Agent.

Combines every upstream agent output into the final answer: recommendations,
advantages/disadvantages, the comparison verdict, review evidence, and an
explicit statement of uncertainty / missing data.

The wording is assembled from real computed outputs — no canned responses.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("shopmate.agents.advisor")

_MONEY = "₹"


def _fmt_price(price: float) -> str:
    return f"{_MONEY}{price:,.0f}"


class ShoppingAdvisorAgent:
    name = "shopping_advisor"

    async def run(
        self,
        understanding: dict[str, Any],
        ranked: Optional[list[dict[str, Any]]] = None,
        comparison: Optional[dict[str, Any]] = None,
        review_analysis: Optional[dict[str, Any]] = None,
        spec_analysis: Optional[dict[str, Any]] = None,
        provider_errors: Optional[list[str]] = None,
        is_sample_data: bool = False,
        intent: str = "product_search",
    ) -> dict[str, Any]:
        ranked = ranked or []
        provider_errors = provider_errors or []
        sections: list[str] = []
        followups: list[str] = []

        # --- opening by intent -------------------------------------------
        if intent == "product_compare" and comparison:
            sections.append(self._compare_intro(understanding, comparison))
        elif intent == "review_analysis" and review_analysis:
            sections.append(self._review_intro(review_analysis))
        elif intent in ("recommendation", "product_search") and ranked:
            cat = understanding.get("category") or "products"
            budget = understanding.get("budget_max")
            budget_txt = f" under {_fmt_price(budget)}" if budget else ""
            sections.append(
                f"Here's what I found for your {cat}{budget_txt} research "
                f"({len(ranked)} option{'s' if len(ranked) != 1 else ''} ranked):"
            )
        elif intent == "general_qa":
            sections.append(
                "I can help you research that. Tell me what you're shopping for "
                "(category + budget) and I'll search, compare and rank real listings."
            )
        else:
            sections.append("Here's my shopping assessment based on the available data:")

        # --- ranked recommendations ---------------------------------------
        if ranked:
            sections.append(self._ranked_section(ranked))
            followups.extend([
                "Compare the top two side by side",
                "What do customers complain about in the top pick?",
                "Find cheaper alternatives to the top pick",
            ])

        # --- comparison verdict -------------------------------------------
        if comparison and comparison.get("products"):
            sections.append(self._verdict_section(comparison))
            followups.append("Which one is better value for money?")

        # --- review evidence ----------------------------------------------
        if review_analysis:
            sections.append(self._review_section(review_analysis))
            followups.append("Show me alternatives with fewer complaints")

        # --- spec narrative -------------------------------------------------
        if spec_analysis:
            sections.append(self._spec_section(spec_analysis))

        # --- uncertainty / data quality (mandatory honesty) -----------------
        caveats: list[str] = []
        if is_sample_data:
            caveats.append(
                "⚠️ Results come from the **sample dataset** (demo data), not a "
                "live merchant feed — prices and availability are illustrative."
            )
        for err in provider_errors[:3]:
            caveats.append(f"Data provider issue: {err}")
        missing = understanding.get("missing_information") or []
        if missing:
            caveats.append(
                "Still needed from you: " + ", ".join(missing) + "."
            )
        if any((r.get("product") or {}).get("rating") is None for r in ranked):
            caveats.append(
                "Some products have no published reviews — they were not "
                "penalised as if they were bad, but review-based confidence is lower."
            )
        if caveats:
            sections.append("**Good to know:**\n" + "\n".join(f"- {c}" for c in caveats))

        # --- closing --------------------------------------------------------
        if understanding.get("followup_question"):
            sections.append(understanding["followup_question"])
        elif not followups:
            followups = [
                "Compare these products side by side",
                "Analyse customer reviews for the top result",
                "Find the best value-for-money option",
            ]

        reply = "\n\n".join(s for s in sections if s)
        return {
            "final_response": reply,
            "suggested_followups": followups[:4],
        }

    # --- section builders ---------------------------------------------------
    def _ranked_section(self, ranked: list[dict[str, Any]]) -> str:
        lines = []
        for i, r in enumerate(ranked[:5], 1):
            p = r.get("product") or {}
            reasons = r.get("reasons") or []
            head = (
                f"**{i}. {p.get('title')}** — {_fmt_price(p.get('price', 0))} "
                f"({p.get('merchant')})"
            )
            score = r.get("final_score")
            score_txt = f"\n   Score: `{score:.0%}`" if isinstance(score, (int, float)) else ""
            top_reasons = [x for x in reasons[:2] if not x.startswith("Sample data")]
            reason_txt = ("\n   Why: " + "; ".join(top_reasons)) if top_reasons else ""
            lines.append(head + score_txt + reason_txt)
        return "\n".join(lines)

    def _compare_intro(self, understanding: dict, comparison: dict) -> str:
        diff = comparison.get("price_difference")
        base = "I compared those products on price and specifications."
        if diff is not None:
            base += f" Price gap: {_fmt_price(diff)}."
        return base

    def _verdict_section(self, comparison: dict) -> str:
        products = comparison.get("products") or []
        by_id = {p["id"]: p for p in products}
        lines = ["**Verdict**"]
        cheapest_id = comparison.get("cheapest_product_id")
        best_id = comparison.get("best_value_id") or cheapest_id
        if cheapest_id and cheapest_id in by_id:
            lines.append(
                f"- Cheapest: {by_id[cheapest_id]['title']} "
                f"({_fmt_price(by_id[cheapest_id]['price'])})"
            )
        if best_id and best_id in by_id and best_id != cheapest_id:
            lines.append(
                f"- Best value: {by_id[best_id]['title']} — it wins on more "
                "specification categories than the alternatives."
            )
        elif best_id and best_id in by_id:
            lines.append(
                f"- Best value: {by_id[best_id]['title']} — cheapest while matching "
                "the competition on the specs that matter."
            )
        stale = comparison.get("stale_products") or []
        if stale:
            lines.append("- ⚠️ Some prices are older than 24h — verify before buying.")
        return "\n".join(lines)

    def _review_intro(self, analysis: dict) -> str:
        count = analysis.get("review_count", 0)
        if count == 0:
            return (
                "I looked for customer reviews of the product you named, but our "
                "data providers have none for it — so there's no sentiment data "
                "to report (I won't invent any)."
            )
        avg = analysis.get("average_rating")
        title = analysis.get("product_title") or "the product"
        return (
            f"Review analysis for **{title}** based on {count} real customer "
            f"review(s)" + (f" averaging {avg}★." if avg else ".")
        )

    def _review_section(self, analysis: dict) -> str:
        if analysis.get("review_count", 0) == 0:
            return (
                "**Customer reviews:** No reviews are available for this product "
                "in our data sources, so I can't judge customer sentiment."
            )
        lines = [f"**Customer reviews** ({analysis.get('review_count', 0)} reviews, "
                 f"avg {analysis.get('average_rating') or 'n/a'}★):"]
        pos = [t["theme"] for t in (analysis.get("positive_themes") or [])[:3]]
        neg = [t["theme"] for t in (analysis.get("negative_themes") or [])[:3]]
        if pos:
            lines.append("- Praised for: " + ", ".join(pos))
        if neg:
            lines.append("- Criticised for: " + ", ".join(neg))
        summary = analysis.get("summary")
        if summary:
            lines.append(f"- {summary}")
        return "\n".join(lines)

    def _spec_section(self, spec: dict) -> str:
        diffs = spec.get("differences") or []
        tradeoffs = spec.get("tradeoffs") or []
        lines: list[str] = []
        if tradeoffs:
            lines.append("**Key trade-offs:**")
            lines.extend(f"- {t}" for t in tradeoffs[:2])
        top = [d for d in diffs if d.get("importance", 0) >= 0.6][:3]
        if top and not tradeoffs:
            lines.append("**Spec highlights:**")
            for d in top:
                expl = d.get("explanation") or ""
                lines.append(f"- `{d['spec']}` differs across options. {expl}".rstrip())
        return "\n".join(lines)
