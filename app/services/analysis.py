"""분석 입력 변환과 여러 리뷰의 RTI 분석 실행을 담당한다."""

from app.analyzers.heuristic import analyze_review
from app.api.schemas import AnalysisResult, IncomingReview, ReviewInput


def analyze_reviews(reviews: list[ReviewInput]) -> list[AnalysisResult]:
    return [analyze_review(review) for review in reviews]


def prepare_review_input(
    incoming: IncomingReview,
    source: str | None = None,
    product_name: str | None = None,
) -> ReviewInput:
    """기존 정규화 스크립트 입력을 현재 분석 DTO로 변환한다.

    ``source``와 ``product_name``은 기존 호출부 호환을 위해 받으며 RTI 계산
    입력에는 사용하지 않는다.
    """
    del source, product_name
    return ReviewInput(
        review_id=incoming.review_id,
        product_id=incoming.product_id or "",
        user_id=incoming.user_id,
        content=incoming.content,
        review_date=incoming.review_date,
        rating=incoming.rating,
        image_count=incoming.image_count,
        quality_score=incoming.quality_score,
        verified_purchase=incoming.verified_purchase,
        repurchase=incoming.repurchase,
        free_trial=incoming.free_trial,
        reviews_written_today=incoming.reviews_written_today,
        similar_review_count=incoming.similar_review_count,
    )
