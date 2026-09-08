"""HTTP 입력 검증과 기존 점수 공식·알고리즘을 회귀 검증한다."""
import itertools
import sys
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.factory import create_app
from ai import analysis
from ai.text_analyzer import calculate_text_score
from ai.behavior_analyzer import calculate_behavior_score
from ai.network_analyzer import calculate_network_score

REVIEW = {
    "review_id": "1001", "content": "배송 빠르고 제품도 좋아요",
    "rating": 5, "user_id": "user1", "review_date": "2026-09-08",
    "verified_purchase": True, "account_age_days": 500,
    "reviews_written_today": 1, "similar_review_count": 0,
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    # Invalid DB settings must not affect startup or requests.
    monkeypatch.setenv("DB_PORT", "not-a-number")
    monkeypatch.setenv("REDIS_PORT", "not-a-number")
    with TestClient(create_app()) as value:
        yield value


def test_health_without_database(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert not {"pymysql", "redis", "app.core.database", "app.repositories.products"} & sys.modules.keys()


def test_single_review(client):
    response = client.post("/api/v1/analyze", json={"product_id": "A001", "reviews": [REVIEW]})
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert response.json()["product_id"] == "A001"
    assert result["review_id"] == "1001"
    assert result["signals"] == {"text": 75, "behavior": 95, "network": 100}
    assert result["rti"] == 88
    assert result["level"] == "safe"
    assert [r["code"] for r in result["reasons"]] == ["SHORT_REVIEW", "NO_IMAGE_ATTACHED"]


def test_batch_order_and_real_algorithms(client):
    reviews = [
        REVIEW,
        {**REVIEW, "review_id": "1002", "content": "좋아요 좋아요!!!",
         "verified_purchase": False, "free_trial": True,
         "reviews_written_today": 3, "similar_review_count": 5, "quality_score": 0.05},
    ]
    with patch.object(analysis, "calculate_text_score", wraps=calculate_text_score) as t, \
         patch.object(analysis, "calculate_behavior_score", wraps=calculate_behavior_score) as b, \
         patch.object(analysis, "calculate_network_score", wraps=calculate_network_score) as n:
        response = client.post("/api/v1/analyze", json={"product_id": "A001", "reviews": reviews})
    assert response.status_code == 200
    assert [r["review_id"] for r in response.json()["results"]] == ["1001", "1002"]
    assert t.call_count == b.call_count == n.call_count == 2
    result = response.json()["results"][1]
    assert result["signals"] == {"text": 40, "behavior": 40, "network": 50}
    assert result["rti"] == 42  # Python round(42.5), not round-half-up.
    assert result["level"] == "danger"


@pytest.mark.parametrize("payload", [
    {}, {"product_id": "A001"}, {"product_id": "A001", "reviews": []},
    {"reviews": [REVIEW]}, {"product_id": "A001", "reviews": [{}]},
    {"product_id": "A001", "reviews": [{**REVIEW, "rating": 6}]},
    {"product_id": "A001", "reviews": [{**REVIEW, "similar_review_count": -1}]},
    {"product_id": "A001", "reviews": [{**REVIEW, "content": None}]},
    {"product_id": "", "reviews": [REVIEW]},
    {"product_id": "A001", "reviews": [{**REVIEW, "unexpected": True}]},
])
def test_invalid_requests(client, payload):
    assert client.post("/api/v1/analyze", json=payload).status_code == 422


@pytest.mark.parametrize("score,level", [(49,"danger"), (50,"warn"), (79,"warn"), (80,"safe")])
def test_level_boundaries(client, score, level):
    with patch.object(analysis, "calculate_text_score", return_value=(score, [])), \
         patch.object(analysis, "calculate_behavior_score", return_value=(score, [])), \
         patch.object(analysis, "calculate_network_score", return_value=(score, [])):
        r = client.post("/api/v1/analyze", json={"product_id": "P", "reviews": [REVIEW]})
    assert r.json()["results"][0]["level"] == level


def test_account_age_does_not_change_score(client):
    results = client.post("/api/v1/analyze", json={"product_id": "P", "reviews": [
        {**REVIEW, "account_age_days": 0}, {**REVIEW, "account_age_days": 9999}
    ]}).json()["results"]
    assert results[0] == results[1]


def test_legacy_apis_retired(client):
    for path in ("products/product-list", "reviews/product-detail", "products/rti-trend",
                 "reviews/report", "products/risk-report"):
        assert client.post("/api/internal/ai/" + path, json={"product_id":"P"}).status_code == 404


def test_google_signal_and_reason_preserved(client, monkeypatch):
    monkeypatch.setattr("ai.text_analyzer.analyze_sentiment",
                        lambda content: {"enabled": True, "score": 0.9, "magnitude": 2.0})
    r = client.post("/api/v1/analyze", json={"product_id":"P", "reviews":[REVIEW]}).json()["results"][0]
    assert r["signals"]["text"] == 70
    assert r["reasons"][1]["code"] == "OVERLY_POSITIVE_SENTIMENT"


def test_parameter_matrix_matches_existing_scoring(client):
    # Direct unchanged functions are the oracle for HTTP mapping and reason order.
    for verified, similar, daily in itertools.product([True, False, "unknown"], [0, 1, 5], [1, 3]):
        review = {**REVIEW, "verified_purchase": verified, "similar_review_count": similar,
                  "reviews_written_today": daily, "image_count": 0, "repurchase": "unknown",
                  "free_trial": "unknown"}
        t, tr = calculate_text_score(review["content"])
        b, br = calculate_behavior_score(review)
        n, nr = calculate_network_score(review)
        result = client.post("/api/v1/analyze", json={"product_id":"P", "reviews":[review]}).json()["results"][0]
        assert result["rti"] == round(t * .4 + b * .35 + n * .25)
        assert result["reasons"] == tr + br + nr
