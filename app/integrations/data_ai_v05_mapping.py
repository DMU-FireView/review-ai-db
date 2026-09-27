"""팀원 분석 결과를 원본 ID로 엄격히 매칭하고 v0.5 평면 응답으로 변환한다."""
from collections.abc import Sequence

from app.contracts.data_ai_v05 import (
    DataAnalyzeRequestV05, DataAnalyzeResponseV05, DataReviewResultV05,
)
from app.services.team_analysis import ReviewAnalysisResult


def map_v05_results(payload: DataAnalyzeRequestV05,
                    evaluated: Sequence[ReviewAnalysisResult]) -> DataAnalyzeResponseV05:
    by_id = {}
    for item in evaluated:
        if item.product_id != payload.product_id or item.review_id in by_id:
            raise ValueError("Mismatched product or duplicate result identity")
        by_id[item.review_id] = item
    if set(by_id) != {review.review_id for review in payload.reviews}:
        raise ValueError("Results must exactly match requested review identities")
    results = []
    for review in payload.reviews:
        item = by_id[review.review_id]
        # 분석기 가용성/값의 모순은 숨기지 않는다. 매퍼는 점수를 만들거나 재계산하지 않는다.
        if item.available != (item.rti is not None):
            raise ValueError("Inconsistent RTI availability")
        for signal in (item.signals.text, item.signals.behavior, item.signals.network):
            if signal.available != (signal.score is not None):
                raise ValueError("Inconsistent signal availability")
        results.append(DataReviewResultV05(
            review_id=review.review_id, rti=item.rti,
            level=item.level.value if item.level is not None else None,
            text_score=item.signals.text.score,
            behavior_score=item.signals.behavior.score,
            network_score=item.signals.network.score,
            # source와 message는 내부에만 남긴다. code 문자열·순서를 임의 변경하지 않는다.
            reasons=[reason.code for reason in item.reasons],
        ))
    return DataAnalyzeResponseV05(platform=payload.platform, product_id=payload.product_id,
                                  review_count=len(results), results=results)
