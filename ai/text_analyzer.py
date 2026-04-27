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

    return max(score, 0), reasons
