import json
from pathlib import Path


INPUT_PATH = Path("data/normalized/reviews.json")
OUTPUT_PATH = Path("output/rti_results.json")


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


def calculate_behavior_score(review):
    score = 100
    reasons = []

    verified_purchase = review.get("verified_purchase")
    repurchase = review.get("repurchase")
    free_trial = review.get("free_trial")
    reviews_written_today = review.get("reviews_written_today")
    image_count = review.get("image_count", 0)

    if verified_purchase is False:
        score -= 30
        reasons.append("구매 이력 미확인")
    elif verified_purchase == "unknown":
        score -= 10
        reasons.append("구매 여부 확인 불가")

    if free_trial is True:
        score -= 10
        reasons.append("체험단/무상 제공 리뷰 가능성")

    if reviews_written_today is not None and reviews_written_today >= 3:
        score -= 15
        reasons.append("동일 작성자의 같은 날짜 다수 리뷰 작성")

    if image_count == 0:
        score -= 5
        reasons.append("이미지 첨부 없음")

    if repurchase is True:
        score += 5
        reasons.append("재구매 리뷰 신호")

    return min(max(score, 0), 100), reasons


def calculate_network_score(review):
    score = 100
    reasons = []

    similar_review_count = review.get("similar_review_count", 0)

    if similar_review_count >= 5:
        score -= 50
        reasons.append("유사 리뷰 네트워크 군집 탐지")
    elif similar_review_count >= 1:
        score -= 15
        reasons.append("일부 유사 리뷰 패턴 탐지")

    return max(score, 0), reasons


def get_level(rti, reasons):
    if rti < 50:
        return "danger"

    if rti < 80:
        return "warn"

    penalty_reasons = [
        reason for reason in reasons
        if reason != "재구매 리뷰 신호"
    ]

    if len(penalty_reasons) > 0:
        return "warn"

    return "safe"


def calculate_rti(review):
    text_score, text_reasons = calculate_text_score(
        review.get("content", ""),
        review.get("quality_score")
    )

    behavior_score, behavior_reasons = calculate_behavior_score(review)
    network_score, network_reasons = calculate_network_score(review)

    rti = round(
        text_score * 0.4
        + behavior_score * 0.35
        + network_score * 0.25
    )

    reasons = text_reasons + behavior_reasons + network_reasons

    return {
        "source": review.get("source"),
        "review_id": review.get("review_id"),
        "user_id": review.get("user_id"),
        "product_id": review.get("product_id"),
        "product_name": review.get("product_name"),
        "rating": review.get("rating"),
        "review_date": review.get("review_date"),
        "rti": rti,
        "level": get_level(rti, reasons),
        "signals": {
            "text": text_score,
            "behavior": behavior_score,
            "network": network_score
        },
        "input_features": {
            "image_count": review.get("image_count"),
            "quality_score": review.get("quality_score"),
            "verified_purchase": review.get("verified_purchase"),
            "repurchase": review.get("repurchase"),
            "free_trial": review.get("free_trial"),
            "reviews_written_today": review.get("reviews_written_today"),
            "similar_review_count": review.get("similar_review_count")
        },
        "reasons": reasons
    }


def main():
    if not INPUT_PATH.exists():
        print(f"정규화 데이터가 없습니다: {INPUT_PATH}")
        print("먼저 아래 명령어를 실행해주세요:")
        print("python ai/normalizer.py")
        return

    with INPUT_PATH.open("r", encoding="utf-8") as file:
        reviews = json.load(file)

    results = [calculate_rti(review) for review in reviews]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print(json.dumps(results[:5], ensure_ascii=False, indent=2))
    print(f"\n총 {len(results)}개 리뷰 RTI 분석 완료")
    print(f"RTI 분석 결과가 저장되었습니다: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()