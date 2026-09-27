"""v0.5 계약·실제 팀원 점수·저장 선행·오류·식별자 매칭을 회귀 검증한다."""
from dataclasses import replace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts.data_ai_v05 import DataAnalyzeRequestV05, DataAnalyzeResponseV05, DataReviewResultV05
from app.factory import create_app
from app.integrations.data_ai_v05_mapping import map_v05_results
from app.repositories.analysis_jobs import SQLiteJobStore
from app.services.team_analysis import AnalysisSignal, AnalysisSignals, ReviewAnalysisInput, analyze_product_reviews


def payload():
    return {"platform": "mall", "product_id": "0007", "reviews": [
        {"review_id": "00:01", "content": "배송 빠르고 제품도 좋아요", "rating": 5,
         "written_at": "2026-09-27T12:00:00"}
    ]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_COLLECTION", "0")
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "0")
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    store = SQLiteJobStore(str(tmp_path / "v05.db"))
    with TestClient(create_app(job_store=store)) as http:
        yield http, store


def test_v05_text_only_and_durable_response(client):
    http, store = client
    response = http.post("/api/v1/data/analyze", json=payload())
    assert response.status_code == 200
    result = response.json()
    assert result == {"platform": "mall", "product_id": "0007", "review_count": 1, "results": [{
        "review_id": "00:01", "rti": 75.0, "level": "warn", "text_score": 75.0,
        "behavior_score": None, "network_score": None, "reasons": ["SHORT_REVIEW"],
    }]}
    saved = store.get(response.headers["X-Analysis-Job-ID"])
    assert saved["status"] == "DONE" and saved["result"] == result
    assert saved["request"] == payload()


def test_v05_duplicate_text_and_available_weight_normalization(client):
    body = payload()
    body["reviews"].append({**body["reviews"][0], "review_id": "0002"})
    result = client[0].post("/api/v1/data/analyze", json=body).json()
    assert [r["review_id"] for r in result["results"]] == ["00:01", "0002"]
    for review in result["results"]:
        assert review["text_score"] == 75 and review["network_score"] == 85
        assert review["behavior_score"] is None
        assert review["rti"] == pytest.approx((75 * .5 + 85 * .2) / .7)
        assert review["level"] == "warn"
        assert review["reasons"] == ["SHORT_REVIEW", "SIMILAR_REVIEW_PATTERN"]


@pytest.mark.parametrize("field,value", [("rating", None), ("rating", 1), ("written_at", None)])
def test_unobserved_behavior_is_not_invented(client, field, value):
    body = payload()
    body["reviews"][0][field] = value
    review = client[0].post("/api/v1/data/analyze", json=body).json()["results"][0]
    assert review["behavior_score"] is None and review["rti"] == 75


@pytest.mark.parametrize("kind", ["empty", "duplicate", "numeric_id", "blank_content", "too_many"])
def test_invalid_batch(client, kind):
    body = payload()
    if kind == "empty": body["reviews"] = []
    elif kind == "duplicate": body["reviews"] *= 2
    elif kind == "numeric_id": body["product_id"] = 7
    elif kind == "blank_content": body["reviews"][0]["content"] = "   "
    else: body["reviews"] *= 501
    assert client[0].post("/api/v1/data/analyze", json=body).status_code == 422


@pytest.mark.parametrize("target", ["create", "complete", "analyzer"])
def test_failures_are_503_not_null_success(client, target):
    http, store = client
    mocker = patch("app.services.data_analysis.analyze_product_reviews", side_effect=RuntimeError("failed")) if target == "analyzer" else patch.object(store, target, side_effect=OSError("failed"))
    with mocker:
        response = http.post("/api/v1/data/analyze", json=payload())
    assert response.status_code == 503 and "results" not in response.json()
    assert "X-Analysis-Job-ID" not in response.headers


@pytest.mark.parametrize("score,level", [(0,"danger"), (49.9,"danger"), (50,"warn"), (79.99,"warn"), (80,"safe"), (100,"safe")])
def test_threshold_contract(score, level):
    result = DataReviewResultV05(review_id="r", rti=score, level=level,
                                 text_score=score, behavior_score=None, network_score=None, reasons=[])
    assert result.level == level


def test_all_unavailable_contract_and_bad_example():
    result = DataReviewResultV05(review_id="r", rti=None, level=None,
                                 text_score=None, behavior_score=None, network_score=None, reasons=[])
    assert result.model_dump()["rti"] is None
    with pytest.raises(ValidationError):
        DataReviewResultV05(**{**result.model_dump(), "rti": 76, "level": "safe", "text_score": 76})
    with pytest.raises(ValidationError):
        DataReviewResultV05(**{**result.model_dump(), "rti": 0, "level": "danger"})


def test_mapping_reorders_and_rejects_wrong_identity():
    body = payload()
    body["reviews"].append({"review_id": "2", "content": "두 번째"})
    request = DataAnalyzeRequestV05(**body)
    evaluated = analyze_product_reviews("0007", [ReviewAnalysisInput(r.review_id,"0007",r.content) for r in request.reviews])
    response = map_v05_results(request, list(reversed(evaluated)))
    assert [r.review_id for r in response.results] == ["00:01", "2"]
    for invalid in (evaluated[:1], (evaluated[0], evaluated[0]),
                    (replace(evaluated[0], product_id="7"), evaluated[1])):
        with pytest.raises(ValueError):
            map_v05_results(request, invalid)


def test_optional_count_and_no_internal_fields():
    response = DataAnalyzeResponseV05(platform="m", product_id="p", results=[])
    assert "review_count" not in response.model_dump(exclude_unset=True)
    assert set(DataReviewResultV05.model_fields) == {
        "review_id", "rti", "level", "text_score", "behavior_score", "network_score", "reasons"}


def test_all_unavailable_mapping_preserves_null_without_recalculation():
    request = DataAnalyzeRequestV05(**payload())
    original = analyze_product_reviews("0007", [ReviewAnalysisInput("00:01", "0007", "테스트")])[0]
    missing = AnalysisSignal(available=False, score=None, unavailable_reasons=("synthetic_missing",))
    unavailable = replace(original, available=False, rti=None, level=None,
                          signals=AnalysisSignals(missing, missing, missing), reasons=())
    result = map_v05_results(request, [unavailable]).results[0]
    assert result.model_dump() == dict(review_id="00:01", rti=None, level=None,
                                      text_score=None, behavior_score=None, network_score=None, reasons=[])
    with pytest.raises(ValueError, match="Inconsistent signal"):
        map_v05_results(request, [replace(unavailable, signals=AnalysisSignals(
            replace(missing, score=0), missing, missing))])
