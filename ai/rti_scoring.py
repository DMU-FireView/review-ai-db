import json
from pathlib import Path


REPETITIVE_KEYWORDS = [
    "최고",
    "대박",
    "강력추천",
    "완전",
    "무조건",
]


def calculate_text_score(content: str) -> tuple[int, list[str]]:
    score = 100
    reasons = []

    for keyword in REPETITIVE_KEYWORDS:
        count = content.count(keyword)
        if count >= 2:
            score -= 25
            reasons.append(f"반복 표현 탐지: '{keyword}' {count}회")

    if len(content) < 30:
        score -= 15
        reasons.append("리뷰 내용이 지나치게 짧음")

    exclamation_count = content.count("!")
    if exclamation_count >= 3:
        score -= 10
        reasons.append("과도한 느낌표 사용")

    return max(score, 0), reasons


def calculate_behavior_score(review: dict) -> tuple[int, list[str]]:
    score = 100
    reasons = []

    if not review["verified_purchase"]:
        score -= 30
        reasons.append("구매 이력 미확인")

    if review["account_age_days"] <= 7:
        score -= 30
        reasons.append("계정 생성 직후 리뷰 작성")

    if review["reviews_written_today"] >= 10:
        score -= 25
        reasons.append("짧은 시간 내 다수 리뷰 작성")

    return max(score, 0), reasons


def calculate_network_score(review: dict) -> tuple[int, list[str]]:
    score = 100
    reasons = []

    if review["similar_review_count"] >= 5:
        score -= 50
        reasons.append("유사 리뷰 네트워크 군집 탐지")
    elif review["similar_review_count"] >= 1:
        score -= 15
        reasons.append("일부 유사 리뷰 패턴 탐지")

    return max(score, 0), reasons


def get_level(rti: int, reasons: list[str]) -> str:
    if rti < 50:
        return "danger"

    if rti < 80:
        return "warn"

    if len(reasons) > 0:
        return "warn"

    return "safe"


def calculate_rti(review: dict) -> dict:
    text_score, text_reasons = calculate_text_score(review["content"])
    behavior_score, behavior_reasons = calculate_behavior_score(review)
    network_score, network_reasons = calculate_network_score(review)

    # v0 기준 가중치
    # 텍스트 40%, 행동 35%, 네트워크 25%
    rti = round(
        text_score * 0.4
        + behavior_score * 0.35
        + network_score * 0.25
    )

    reasons = text_reasons + behavior_reasons + network_reasons

    return {
        "review_id": review["review_id"],
        "user_id": review["user_id"],
        "product_id": review["product_id"],
        "rti": rti,
        "level": get_level(rti, reasons),
        "signals": {
            "text": text_score,
            "behavior": behavior_score,
            "network": network_score,
        },
        "reasons": reasons,
    }


def main():
    data_path = Path("data/sample_reviews.json")
    output_path = Path("output/rti_results.json")

    with data_path.open("r", encoding="utf-8") as file:
        reviews = json.load(file)

    results = [calculate_rti(review) for review in reviews]

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nRTI 분석 결과가 저장되었습니다: {output_path}")


if __name__ == "__main__":
    main()