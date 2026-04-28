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


def calculate_text_score(content, quality_score=None):
    score = 100
    reasons = []

    content = content or ""

    for keyword in REPETITIVE_KEYWORDS:
        count = content.count(keyword)

        if count >= 2:
            score -= 15
            reasons.append(f"반복 표현 탐지: '{keyword}' {count}회")

    if len(content.strip()) < 20:
        score -= 25
        reasons.append("리뷰 내용이 지나치게 짧음")

    if content.count("!") >= 3:
        score -= 10
        reasons.append("과도한 느낌표 사용")

    if quality_score is not None and quality_score < 0.1:
        score -= 10
        reasons.append("리뷰 품질 점수 낮음")

    # Google Cloud Natural Language API 감성 분석 보조 신호
    # 현재 기본값은 mock/fallback 모드이므로 점수에는 영향을 주지 않습니다.
    sentiment_result = analyze_sentiment(content)

    if sentiment_result.get("enabled"):
        sentiment_score = sentiment_result.get("score", 0.0)
        sentiment_magnitude = sentiment_result.get("magnitude", 0.0)

        # v0에서는 강한 과장/극단 감성 신호만 소폭 반영
        if sentiment_score > 0.8 and sentiment_magnitude > 1.5:
            score -= 5
            reasons.append("과도하게 긍정적인 감성 표현 탐지")

    return max(score, 0), reasons
