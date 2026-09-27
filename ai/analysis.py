"""기존 점수 공식과 사유 순서를 보존하며 세 분석기를 결합한다."""

from ai.behavior_analyzer import calculate_behavior_score
from ai.network_analyzer import calculate_network_score
from ai.text_analyzer import calculate_text_score

from app.api.schemas import (
    AnalysisResult,
    InputFeatures,
    ReasonObject,
    ReviewInput,
    SignalScores,
)


def analyze_review(review: ReviewInput) -> AnalysisResult:
    text_score, text_reasons = calculate_text_score(
        review.content, review.quality_score
    )
    review_data = review.model_dump()
    behavior_score, behavior_reasons = calculate_behavior_score(review_data)
    network_score, network_reasons = calculate_network_score(review_data)

    rti = round(
        text_score * 0.4 + behavior_score * 0.35 + network_score * 0.25
    )
    level = "danger" if rti < 50 else "warn" if rti < 80 else "safe"
    reasons = [
        ReasonObject(code=reason["code"], message=reason["message"])
        for reason in text_reasons + behavior_reasons + network_reasons
    ]

    return AnalysisResult(
        review_id=review.review_id,
        content=review.content,
        author=review.user_id,
        date=review.review_date,
        rti=rti,
        level=level,
        signals=SignalScores(
            text=int(text_score),
            behavior=int(behavior_score),
            network=int(network_score),
        ),
        input_features=InputFeatures(
            image_count=review.image_count,
            quality_score=review.quality_score,
            verified_purchase=str(review.verified_purchase),
            repurchase=str(review.repurchase),
            free_trial=str(review.free_trial),
            reviews_written_today=review.reviews_written_today,
            similar_review_count=review.similar_review_count,
        ),
        reasons=reasons,
    )
