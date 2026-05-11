def make_reason(code, message):
    return {
        "code": code,
        "message": message
    }


def calculate_network_score(review):
    score = 100
    reasons = []

    similar_review_count = review.get("similar_review_count", 0)

    if similar_review_count >= 5:
        score -= 50
        reasons.append(
            make_reason(
                "SIMILAR_REVIEW_CLUSTER",
                "유사 리뷰 네트워크 군집 탐지"
            )
        )
    elif similar_review_count >= 1:
        score -= 15
        reasons.append(
            make_reason(
                "SIMILAR_REVIEW_PATTERN",
                "일부 유사 리뷰 패턴 탐지"
            )
        )

    return max(score, 0), reasons
