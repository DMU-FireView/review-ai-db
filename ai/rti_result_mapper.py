"""Map saved RTI scores into the current analysis response model."""


def build_analysis_result_from_saved_score(review, saved_score):
    """Build an AnalysisResult from a ReviewInput and a saved RTI score dict.

    This helper intentionally does not recalculate RTI, level, signals, or
    reasons. It only maps persisted score values into the current response
    shape.
    """
    if saved_score is None:
        return None

    from main import AnalysisResult, InputFeatures, ReasonObject, SignalScores

    signals = saved_score.get("signals") or {}
    reasons = _build_reason_objects(saved_score.get("reasons"), ReasonObject)

    return AnalysisResult(
        review_id=review.review_id,
        content=review.content,
        author=review.user_id,
        date=review.review_date,
        rti=saved_score.get("rti"),
        level=saved_score.get("level"),
        signals=SignalScores(
            text=signals.get("text", 0),
            behavior=signals.get("behavior", 0),
            network=signals.get("network", 0),
        ),
        input_features=InputFeatures(
            rating=review.rating,
            image_count=review.image_count,
            quality_score=review.quality_score,
            verified_purchase=review.verified_purchase,
            repurchase=review.repurchase,
            free_trial=review.free_trial,
            reviews_written_today=review.reviews_written_today,
            similar_review_count=review.similar_review_count,
        ),
        reasons=reasons,
    )


def _build_reason_objects(raw_reasons, reason_model):
    if not isinstance(raw_reasons, list):
        return []

    reasons = []
    for reason in raw_reasons:
        if not isinstance(reason, dict):
            continue

        code = reason.get("code")
        message = reason.get("message")
        if code is None or message is None:
            continue

        reasons.append(reason_model(code=code, message=message))

    return reasons
