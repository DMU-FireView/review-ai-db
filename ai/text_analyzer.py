from sentiment_client import analyze_sentiment


REPETITIVE_KEYWORDS = [
    "최고",
    "대박",
    "강력추천",
    "완전",
    "무조건",
    "좋아요",
    "만족",
]


def make_reason(code, message):
    return {
        "code": code,
        "message": message
    }


def calculate_text_score(content, quality_score=None):
    score = 100
    reasons = []

    content = content or ""

    for keyword in REPETITIVE_KEYWORDS:
        count = content.count(keyword)
        if count >= 2:
            score -= 15
            reasons.append({
                "code": "REPETITIVE_WORD",
                "message": f"반복 표현 탐지: '{keyword}' {count}회"
            })

    if len(content.strip()) < 20:
        score -= 25
        reasons.append({
            "code": "SHORT_CONTENT",
            "message": "리뷰 내용이 지나치게 짧음"
        })

    if content.count("!") >= 3:
        score -= 10
        reasons.append({
            "code": "EXCESSIVE_EXCLAMATION",
            "message": "과도한 느낌표 사용"
        })

    if quality_score is not None and quality_score < 0.1:
        score -= 10
        reasons.append({
            "code": "LOW_QUALITY_SCORE",
            "message": "리뷰 품질 점수 낮음"
        })

    sentiment_result = analyze_sentiment(content)

    if sentiment_result.get("enabled"):
        sentiment_score = sentiment_result.get("score", 0.0)
        sentiment_magnitude = sentiment_result.get("magnitude", 0.0)

        if sentiment_score > 0.8 and sentiment_magnitude > 1.5:
            score -= 5
            reasons.append(
                make_reason(
                    "OVERLY_POSITIVE_SENTIMENT",
                    "과도하게 긍정적인 감성 표현 탐지"
                )
            )

    return max(score, 0), reasons
