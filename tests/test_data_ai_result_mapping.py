"""원본 ID 보존, 명시적 결과 매핑, null 상태와 오매칭 거절을 검증한다."""
import pytest
from pydantic import ValidationError

from app.contracts.data_ai_result import (
    AnalysisReason, DataAIResult, IdentifiedEvaluation, ReviewEvaluation,
    ReviewIdentity, SignalResult, Signals,
)
from app.integrations.data_ai_result_mapping import map_data_ai_result


def identity(review_id="001", platform="kurly", product_id="0007"):
    return ReviewIdentity(platform=platform, product_id=product_id, review_id=review_id)


def evaluation(score=82.4):
    # 매핑 검증용 합성 점수이며 실제 RTI 공식의 기대값이 아니다.
    return ReviewEvaluation(
        rti_available=True, rti=score, level="safe",
        signals=Signals(
            text=SignalResult(available=True, score=85.0, unavailable_reasons=[]),
            behavior=SignalResult(available=False, score=None,
                                  unavailable_reasons=["insufficient_behavior_evidence"]),
            network=SignalResult(available=True, score=76.0, unavailable_reasons=[]),
        ),
        reasons=[AnalysisReason(source="network", code="FUTURE_CODE",
                                message="합성 테스트 근거")],
    )


def bound(source, result=None):
    return IdentifiedEvaluation(identity=source, evaluation=result or evaluation())


def test_exact_target_json_preserves_ids_and_request_order():
    sources = [identity("00:01"), identity("0002")]
    values = [bound(sources[1], evaluation(81.75)), bound(sources[0])]
    before = [item.model_dump() for item in values]
    result = map_data_ai_result(sources, values).model_dump(mode="json")
    assert result["platform"] == "kurly"
    assert result["product_id"] == "0007"
    assert result["review_count"] == 2
    assert [r["review_id"] for r in result["results"]] == ["00:01", "0002"]
    assert [r["rti"] for r in result["results"]] == [82.4, 81.75]
    assert result["results"][0] == {"review_id": "00:01", **evaluation().model_dump(mode="json")}
    assert set(result) == {"platform", "product_id", "review_count", "results"}
    assert [item.model_dump() for item in values] == before


def test_no_signal_and_null_rti_are_preserved():
    unavailable = SignalResult(available=False, score=None, unavailable_reasons=["no_evidence"])
    result = ReviewEvaluation(
        rti_available=False, rti=None, level=None,
        signals=Signals(text=unavailable, behavior=unavailable, network=unavailable),
        reasons=[],
    )
    mapped = map_data_ai_result([identity()], [bound(identity(), result)])
    assert mapped.results[0].rti is None
    assert mapped.results[0].level is None
    assert mapped.results[0].reasons == []
    assert mapped.results[0].signals.behavior.score is None


def test_text_only_does_not_recalculate_score_or_level():
    data = evaluation(12.345).model_dump()
    data["signals"]["network"] = data["signals"]["behavior"].copy()
    data["reasons"] = []
    # 일부러 기존 safe 경계와 다른 합성 등급: 매퍼가 재판정하면 안 된다.
    mapped = map_data_ai_result([identity()], [bound(identity(), ReviewEvaluation(**data))])
    assert mapped.results[0].rti == 12.345
    assert mapped.results[0].level == "safe"


@pytest.mark.parametrize("other", [
    identity(platform="other"), identity(product_id="other"), identity("other"),
])
def test_composite_identity_prevents_wrong_binding(other):
    with pytest.raises(ValueError, match="exactly match"):
        map_data_ai_result([identity()], [bound(other)])


@pytest.mark.parametrize("requested,evaluated", [
    ([], []),
    ([identity(), identity()], [bound(identity())]),
    ([identity()], [bound(identity()), bound(identity())]),
    ([identity()], []),
    ([identity()], [bound(identity()), bound(identity("extra"))]),
    ([identity(), identity(platform="other")], []),
    ([identity(), identity(product_id="other")], []),
])
def test_reject_ambiguous_or_partial_batches(requested, evaluated):
    with pytest.raises(ValueError):
        map_data_ai_result(requested, evaluated)


@pytest.mark.parametrize("changes", [
    {"platform": 1}, {"product_id": 7}, {"review_id": 1},
    {"platform": ""}, {"review_id": ""},
])
def test_identifiers_are_not_coerced(changes):
    with pytest.raises(ValidationError):
        ReviewIdentity(**{**identity().model_dump(), **changes})


def test_identifiers_not_split_trimmed_or_case_folded():
    source = identity(" a:b ", platform="KURLY", product_id="00:07")
    mapped = map_data_ai_result([source], [bound(source)])
    assert (mapped.platform, mapped.product_id, mapped.results[0].review_id) == (
        "KURLY", "00:07", " a:b ")


@pytest.mark.parametrize("changes", [
    {"available": False, "score": 85},
    {"available": True, "score": None},
    {"unavailable_reasons": ["cannot_calculate"]},
    {"score": -1}, {"score": 101}, {"score": float("nan")},
    {"score": float("inf")}, {"score": "85"}, {"score": True},
    {"available": "true"},
])
def test_signal_invariants(changes):
    with pytest.raises(ValidationError):
        SignalResult(**{**evaluation().signals.text.model_dump(), **changes})


@pytest.mark.parametrize("changes", [
    {"rti_available": False}, {"rti": None}, {"level": None},
    {"rti": float("nan")}, {"rti": 101}, {"level": "unknown"},
])
def test_rti_invariants(changes):
    with pytest.raises(ValidationError):
        ReviewEvaluation(**{**evaluation().model_dump(), **changes})


def test_no_available_signal_cannot_claim_available_rti():
    data = evaluation().model_dump()
    unavailable = data["signals"]["behavior"]
    data["signals"] = {name: unavailable for name in ("text", "behavior", "network")}
    with pytest.raises(ValidationError):
        ReviewEvaluation(**data)


def test_reason_source_is_explicit_and_codes_are_extensible():
    assert evaluation().reasons[0].code == "FUTURE_CODE"
    with pytest.raises(ValidationError):
        AnalysisReason(code="ANY", message="missing source")
    with pytest.raises(ValidationError):
        AnalysisReason(source="guessed", code="ANY", message="wrong source")


def test_mapper_revalidates_modified_models():
    invalid = evaluation().model_copy(update={"rti": -10})
    with pytest.raises(ValidationError):
        map_data_ai_result([identity()], [bound(identity(), invalid)])


def test_output_count_and_duplicates_are_checked():
    output = map_data_ai_result([identity()], [bound(identity())]).model_dump()
    with pytest.raises(ValidationError):
        DataAIResult(**{**output, "review_count": 2})
    with pytest.raises(ValidationError):
        DataAIResult(**{**output, "review_count": 2, "results": output["results"] * 2})


def test_legacy_result_is_not_silently_assumed_available():
    with pytest.raises(ValidationError):
        ReviewEvaluation(rti=88, level="safe",
                         signals={"text": 75, "behavior": 95, "network": 100},
                         reasons=[])
