"""검토용 요청·응답 모델과 원본 ID 연결을 테스트하며 운영 API와 분리한다."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts.data_ai_request import DataAIRequest
from app.contracts.data_ai_response import DataAIResponse
from app.contracts.data_ai_result import IdentifiedEvaluation
from app.integrations.data_ai_result_mapping import map_data_ai_result
from app.api.schemas import AnalyzeRequest
from app.factory import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "data_ai_v04"


def request_payload():
    return {
        "platform": "kurly",
        "product_id": "1001196970",
        "reviews": [{
            "review_id": "135039521", "content": "크리미한 카레라 난이랑 같이 먹었어요",
            "rating": 5, "written_at": "2026-06-26T00:31:53",
        }],
    }


def response_payload():
    return json.loads((FIXTURES / "normal.response.json").read_text(encoding="utf-8"))


def test_pdf_request_example_roundtrip():
    payload = request_payload()
    result = DataAIRequest.model_validate_json(json.dumps(payload))
    assert result.model_dump(mode="json") == payload
    assert DataAIRequest.model_validate_json(result.model_dump_json()) == result


def test_minimal_request_has_no_fabricated_fields():
    payload = request_payload()
    del payload["reviews"][0]["rating"]
    del payload["reviews"][0]["written_at"]
    result = DataAIRequest.model_validate(payload)
    assert result.reviews[0].rating is None
    assert result.reviews[0].written_at is None
    assert result.model_dump(mode="json", exclude_unset=True) == payload
    assert "user_id" not in result.reviews[0].model_dump()
    assert "similar_review_count" not in result.reviews[0].model_dump()


def test_explicit_null_and_missing_can_be_distinguished():
    payload = request_payload()
    payload["reviews"][0].update(rating=None, written_at=None)
    result = DataAIRequest.model_validate(payload)
    assert result.model_dump(exclude_unset=True) == payload
    assert {"rating", "written_at"} <= result.reviews[0].model_fields_set


@pytest.mark.parametrize("field", ["platform", "product_id", "reviews"])
def test_required_top_level_fields(field):
    payload = request_payload()
    del payload[field]
    with pytest.raises(ValidationError):
        DataAIRequest.model_validate(payload)


@pytest.mark.parametrize("field", ["review_id", "content"])
def test_required_review_fields(field):
    payload = request_payload()
    del payload["reviews"][0][field]
    with pytest.raises(ValidationError):
        DataAIRequest.model_validate(payload)


@pytest.mark.parametrize("field,value", [
    ("review_id", 1), ("review_id", ""), ("content", ""), ("content", None),
    ("rating", "5"), ("rating", True), ("rating", float("nan")),
    ("rating", float("inf")), ("written_at", 123),
])
def test_invalid_review_field_types(field, value):
    payload = request_payload()
    payload["reviews"][0][field] = value
    with pytest.raises(ValidationError):
        DataAIRequest.model_validate(payload)


def test_empty_batch_and_unknown_fields_rejected():
    for payload in (
        {**request_payload(), "reviews": []},
        {**request_payload(), "unexpected": True},
        {**request_payload(), "reviews": [{"review_id": "r", "content": "ok", "user_id": "u"}]},
    ):
        with pytest.raises(ValidationError):
            DataAIRequest.model_validate(payload)


def test_optional_values_are_preserved_without_date_conversion():
    payload = request_payload()
    payload["reviews"][0].update(rating=4.5, written_at="2026-09-19T12:30:00+09:00")
    assert DataAIRequest.model_validate(payload).model_dump(mode="json") == payload


def test_request_identities_connect_to_existing_mapper():
    source = json.loads((FIXTURES / "normal.mapping-input.json").read_text(encoding="utf-8"))
    requested = DataAIRequest(
        platform=source["requested"][0]["platform"],
        product_id=source["requested"][0]["product_id"],
        reviews=[{"review_id": item["review_id"], "content": "합성 입력"} for item in source["requested"]],
    )
    result = map_data_ai_result(
        requested.review_identities(),
        [IdentifiedEvaluation.model_validate(item) for item in source["evaluated"]],
    )
    assert DataAIResponse.model_validate(result.model_dump()).model_dump() == response_payload()
    assert result.results[0].review_id == "00:01"
    assert result.product_id == "0007"


def test_response_count_can_be_omitted_or_explicit_null():
    payload = response_payload()
    del payload["review_count"]
    parsed = DataAIResponse.model_validate(payload)
    assert parsed.model_dump(mode="json", exclude_unset=True) == payload
    explicit = DataAIResponse.model_validate({**payload, "review_count": None})
    assert "review_count" in explicit.model_fields_set
    assert "review_count" not in parsed.model_fields_set


@pytest.mark.parametrize("case", [
    "normal", "behavior_unavailable", "network_unavailable", "all_unavailable",
])
def test_all_existing_responses_are_accepted(case):
    payload = json.loads((FIXTURES / f"{case}.response.json").read_text(encoding="utf-8"))
    assert DataAIResponse.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize("count", [-1, 1, "2", True])
def test_invalid_response_count(count):
    with pytest.raises(ValidationError):
        DataAIResponse.model_validate({**response_payload(), "review_count": count})


def test_duplicate_results_rejected_even_when_count_omitted():
    payload = response_payload()
    del payload["review_count"]
    payload["results"] = [payload["results"][0]] * 2
    with pytest.raises(ValidationError):
        DataAIResponse.model_validate(payload)


def test_request_schema_required_fields():
    schema = DataAIRequest.model_json_schema()
    assert set(schema["required"]) == {"platform", "product_id", "reviews"}
    assert set(schema["$defs"]["DataAIReview"]["required"]) == {"review_id", "content"}
    assert "review_count" not in DataAIResponse.model_json_schema()["required"]


def test_existing_api_contract_is_not_replaced(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("ENABLE_EXPERIMENTAL_COLLECTION", "0")
    schema = create_app().openapi()
    assert "DataAIRequest" not in schema["components"]["schemas"]
    assert "DataAIResponse" not in schema["components"]["schemas"]
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(request_payload())
