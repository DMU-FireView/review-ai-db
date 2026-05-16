import json
from pathlib import Path

from text_analyzer import calculate_text_score
from behavior_analyzer import calculate_behavior_score
from network_analyzer import calculate_network_score


INPUT_PATH = Path("data/normalized/reviews.json")
OUTPUT_PATH = Path("output/rti_results.json")


def get_level(rti, reasons):
    if rti < 50:
        return "danger"

    if rti < 80:
        return "warn"

    # 이 부분을 '문자열' 비교에서 '딕셔너리의 code' 비교로 수정!
    penalty_reasons = [
        reason for reason in reasons
        if reason.get("code") != "REPURCHASE_SIGNAL"
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

    # v0 기준 가중치
    # Text 40%, Behavior 35%, Network 25%
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

    # 현재 v0는 normalized 리뷰 배열 전체를 batch로 분석합니다.
    results = [calculate_rti(review) for review in reviews]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print(json.dumps(results[:5], ensure_ascii=False, indent=2))
    print(f"\n총 {len(results)}개 리뷰 RTI batch 분석 완료")
    print(f"RTI 분석 결과가 저장되었습니다: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
