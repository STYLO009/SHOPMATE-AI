"""Recommendation ranking + review analysis tests."""

from app.utils.ranking import (
    NEUTRAL_REVIEW_SCORE,
    FactorScores,
    get_weights,
    score_budget,
    score_review,
    score_spec_match,
    weighted_final,
)


# --- unit: ranking factors -------------------------------------------------

def test_weights_sum_to_one_and_override_per_category():
    base = get_weights(None)
    assert abs(sum(base.values()) - 1.0) < 1e-6
    laptop = get_weights("laptop")
    assert abs(sum(laptop.values()) - 1.0) < 1e-6
    assert laptop["spec"] > base["spec"]  # laptops weigh specs more


def test_budget_suitability_prefers_headroom():
    under, _ = score_budget(50000, budget_max=60000)
    at_cap, _ = score_budget(60000, budget_max=60000)
    over, over_reason = score_budget(75000, budget_max=60000)
    assert under > at_cap > over
    assert "Over budget" in over_reason


def test_missing_reviews_never_score_perfect():
    score, reason = score_review(None, None)
    assert score == NEUTRAL_REVIEW_SCORE
    assert score < 1.0
    assert "No review data" in reason
    zero_score, _ = score_review(4.5, 0)
    assert zero_score == NEUTRAL_REVIEW_SCORE  # count 0 = no data


def test_high_rated_with_many_reviews_scores_high():
    score, _ = score_review(4.8, 500)
    assert score > 0.8


def test_spec_match_detects_unmet_requirements():
    score, reasons, missing = score_spec_match(
        {"ram_min": 16, "gpu_required": True},
        {"ram_gb": 8, "gpu": "Intel UHD (integrated)"},
        "laptop",
    )
    assert score < 0.5
    assert any(r.startswith("✘") for r in reasons)

    good, good_reasons, _ = score_spec_match(
        {"ram_min": 16, "gpu_required": True},
        {"ram_gb": 16, "gpu": "NVIDIA RTX 4050 6GB"},
        "laptop",
    )
    assert good == 1.0
    assert any(r.startswith("✔") for r in good_reasons)


def test_weighted_final_uses_configured_weights():
    perfect = FactorScores(1.0, 1.0, 1.0, 1.0)
    zero = FactorScores(0.0, 0.0, 0.0, 0.0)
    assert weighted_final(perfect, "laptop") == 1.0
    assert weighted_final(zero, "laptop") == 0.0


# --- integration: /api/recommendations ------------------------------------

def test_recommendations_are_explainable(auth_client):
    resp = auth_client.post(
        "/api/recommendations",
        json={"query": "gaming laptop under 60000", "budget_max": 60000,
              "usage": ["gaming"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ranked"], "expected ranked products"
    assert abs(sum(body["weights"].values()) - 1.0) < 1e-3
    top = body["ranked"][0]
    assert 0 <= top["final_score"] <= 1
    assert set(top["factor_scores"]) == {
        "spec_match", "budget_suitability",
        "preference_similarity", "review_quality",
    }
    assert top["reasons"], "ranking must be explainable"
    # Sorted by score descending
    scores = [r["final_score"] for r in body["ranked"]]
    assert scores == sorted(scores, reverse=True)


def test_recommendations_respect_budget(auth_client):
    resp = auth_client.post(
        "/api/recommendations",
        json={"query": "wireless headphones", "budget_max": 3000,
              "category": "headphones"},
    )
    assert resp.status_code == 200
    for r in resp.json()["ranked"]:
        assert r["product"]["price"] <= 3000


def test_recommendations_never_invent_missing_reviews(auth_client):
    resp = auth_client.post(
        "/api/recommendations",
        json={"query": "Nova Core 5G smartphone", "category": "smartphone"},
    )
    assert resp.status_code == 200
    for r in resp.json()["ranked"]:
        if r["product"]["review_count"] == 0:
            assert r["factor_scores"]["review_quality"] <= NEUTRAL_REVIEW_SCORE


# --- integration: /api/reviews/analyze ------------------------------------

def test_review_analysis_uses_real_reviews(auth_client):
    resp = auth_client.post("/api/reviews/analyze",
                            json={"product_id": "SMP-PHN-002"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["review_count"] > 0
    assert body["positive_themes"] or body["negative_themes"]
    assert body["summary"]
    # Every theme must map to an actual review mention count.
    for t in body["positive_themes"] + body["negative_themes"]:
        assert t["mentions"] >= 1


def test_review_analysis_reports_missing_reviews(auth_client):
    resp = auth_client.post("/api/reviews/analyze",
                            json={"product_id": "SMP-PHN-006"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["review_count"] == 0
    assert "No customer reviews" in body["summary"]
    assert body["positive_themes"] == []
    assert body["negative_themes"] == []


def test_review_analysis_unknown_product(auth_client):
    resp = auth_client.post("/api/reviews/analyze",
                            json={"product_id": "SMP-NOPE-000"})
    assert resp.status_code == 404
