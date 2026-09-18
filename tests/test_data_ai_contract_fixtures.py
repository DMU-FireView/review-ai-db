"""디스크의 합성 JSON으로 v0.4 결과 계약과 순수 매퍼를 회귀 검증한다."""
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts.data_ai_result import DataAIResult, IdentifiedEvaluation, ReviewIdentity
from app.integrations.data_ai_result_mapping import map_data_ai_result

FIXTURES = Path(__file__).parent / "fixtures" / "data_ai_v04"
CASES = ("normal", "behavior_unavailable", "network_unavailable", "all_unavailable")


def load_case(name, kind):
    return json.loads((FIXTURES / f"{name}.{kind}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", CASES)
def test_file_contract_and_mapping_roundtrip(name):
    source = load_case(name, "mapping-input")
    expected = load_case(name, "response")
    original = copy.deepcopy(source)
    requested = [ReviewIdentity.model_validate(value) for value in source["requested"]]
    evaluated = [IdentifiedEvaluation.model_validate(value) for value in source["evaluated"]]
    response = map_data_ai_result(requested, evaluated)
    # 기대값은 테스트 실행 중 계산하지 않고 별도 JSON 파일과 전체 비교한다.
    assert response.model_dump(mode="json") == expected
    assert DataAIResult.model_validate_json(response.model_dump_json()).model_dump(mode="json") == expected
    assert DataAIResult.model_validate(expected).review_count == len(expected["results"])
    assert source == original
    assert [r.review_id for r in response.results] == [r.review_id for r in requested]
    assert response.product_id == "0007"
    assert response.results[0].review_id == "00:01"


@pytest.mark.parametrize("name,flags", [
    ("normal", (True, True, True)),
    ("behavior_unavailable", (True, False, True)),
    ("network_unavailable", (True, True, False)),
    ("all_unavailable", (False, False, False)),
])
def test_fixture_semantics_are_explicit(name, flags):
    payload = load_case(name, "response")
    for result in payload["results"]:
        for key, expected_flag in zip(("text", "behavior", "network"), flags):
            signal = result["signals"][key]
            assert signal["available"] is expected_flag
            if expected_flag:
                assert signal["score"] is not None
                assert signal["unavailable_reasons"] == []
            else:
                assert signal["score"] is None
                assert signal["unavailable_reasons"]
        assert result["rti_available"] is any(flags)
        if not any(flags):
            assert result["rti"] is None and result["level"] is None
            assert result["reasons"] == []
    # 위 any(flags)는 이 네 합성 fixture의 기대 상태일 뿐 RTI 정책이 아니다.


def test_batch_results_reorder_without_changing_reasons_or_scores():
    source = load_case("normal", "mapping-input")
    assert source["requested"][0] != source["evaluated"][0]["identity"]
    mapped = map_data_ai_result(
        [ReviewIdentity(**v) for v in source["requested"]],
        [IdentifiedEvaluation(**v) for v in source["evaluated"]],
    )
    assert mapped.results[1].reasons[0].source == "network"
    assert mapped.results[1].reasons[0].message == "합성 테스트용 유사 패턴 근거"
    assert mapped.results[0].reasons == []


@pytest.mark.parametrize("name,signal_key", [
    ("behavior_unavailable", "behavior"),
    ("network_unavailable", "network"),
    ("all_unavailable", "text"),
])
@pytest.mark.parametrize("replacement", [0, 100])
def test_unavailable_cannot_be_replaced_by_zero_or_full_score(name, signal_key, replacement):
    payload = load_case(name, "response")
    payload["results"][0]["signals"][signal_key]["score"] = replacement
    with pytest.raises(ValidationError):
        DataAIResult.model_validate(payload)


@pytest.mark.parametrize("field", ["score", "available", "unavailable_reasons"])
def test_required_signal_fields_cannot_be_omitted(field):
    payload = load_case("normal", "response")
    del payload["results"][0]["signals"]["text"][field]
    with pytest.raises(ValidationError):
        DataAIResult.model_validate(payload)


@pytest.mark.parametrize("patch", [
    {"rti_available": True},
    {"rti": 0},
    {"level": "danger"},
])
def test_all_unavailable_must_not_claim_a_result(patch):
    payload = load_case("all_unavailable", "response")
    payload["results"][0].update(patch)
    with pytest.raises(ValidationError):
        DataAIResult.model_validate(payload)


@pytest.mark.parametrize("key,value", [
    ("platform", "different-mall"), ("product_id", "7"), ("review_id", "1"),
])
def test_fixture_source_identity_mismatch_fails(key, value):
    payload = load_case("normal", "mapping-input")
    payload["evaluated"][0]["identity"][key] = value
    with pytest.raises(ValueError, match="exactly match"):
        map_data_ai_result(
            [ReviewIdentity(**v) for v in payload["requested"]],
            [IdentifiedEvaluation(**v) for v in payload["evaluated"]],
        )


def test_fixture_catalog_has_no_uncovered_json_files():
    assert {p.name for p in FIXTURES.glob("*.json")} == {
        f"{name}.{kind}.json" for name in CASES for kind in ("mapping-input", "response")
    }
