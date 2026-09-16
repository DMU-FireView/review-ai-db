"""원본 복합 식별자로 계산 결과를 매칭해 v0.4 목표 응답을 만드는 순수 매퍼."""
from collections.abc import Sequence

from app.contracts.data_ai_result import (
    DataAIResult,
    IdentifiedEvaluation,
    ReviewIdentity,
    ReviewResult,
)


def map_data_ai_result(
    requested: Sequence[ReviewIdentity],
    evaluated: Sequence[IdentifiedEvaluation],
) -> DataAIResult:
    """요청 순서대로 전체 결과를 반환한다. 모호한/부분 매칭은 거절한다.

    이 준비용 경계는 한 플랫폼·상품의 비어 있지 않은 완전 배치를 요구한다.
    부분 결과·빈 배치·중복 요청 정책은 최종 API 합의 뒤 별도로 연결한다.
    분석 함수/DB/HTTP를 호출하거나 점수·등급·사유 source를 추정하지 않는다.
    """
    # model_copy/외부 변경으로 검증을 우회한 객체도 경계에서 다시 검사한다.
    sources = [ReviewIdentity.model_validate(item.model_dump()) for item in requested]
    results = [
        IdentifiedEvaluation.model_validate(item.model_dump()) for item in evaluated
    ]
    if not sources:
        raise ValueError("Empty requested batch is not supported by this mapper")
    product = (sources[0].platform, sources[0].product_id)
    if any((item.platform, item.product_id) != product for item in sources):
        raise ValueError("Requested batch must belong to one platform and product")
    if len(set(sources)) != len(sources):
        raise ValueError("Duplicate requested review identity")

    by_identity = {}
    for result in results:
        if result.identity in by_identity:
            raise ValueError("Duplicate evaluated review identity")
        by_identity[result.identity] = result.evaluation
    if set(by_identity) != set(sources):
        raise ValueError("Evaluated identities must exactly match requested identities")

    return DataAIResult(
        platform=product[0],
        product_id=product[1],
        review_count=len(sources),
        results=[
            ReviewResult(
                review_id=source.review_id,
                **by_identity[source].model_dump(),
            )
            for source in sources
        ],
    )
