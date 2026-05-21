import json
from pathlib import Path

<<<<<<< Updated upstream
from text_analyzer import calculate_text_score
from behavior_analyzer import calculate_behavior_score
from network_analyzer import calculate_network_score
=======
# main.py의 Clean Payload 구조와 분석 엔진을 그대로 사용
from main import IncomingReview, prepare_review_input, analyze_single_review
>>>>>>> Stashed changes


INPUT_PATH = Path("data/normalized/reviews.json")
OUTPUT_PATH = Path("output/rti_results.json")


<<<<<<< Updated upstream
def get_level(rti, reasons):
    if rti < 50:
        return "danger"

    if rti < 80:
        return "warn"

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
=======
def load_reviews(data):
    """
    data/normalized/reviews.json 구조가
    배열이든, {"reviews": [...]} 형태든 처리
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if isinstance(data.get("reviews"), list):
            return data["reviews"]

    return []


def get_product_url(review: dict):
    """
    빈님 데이터: page_url
    하연 데이터: productUrl
    최종 통일 필드: product_url
    """
    return (
        review.get("product_url")
        or review.get("page_url")
        or review.get("productUrl")
    )


def to_incoming_review(review: dict) -> IncomingReview:
    """
    정규화된 리뷰 1개를 main.py의 IncomingReview 구조로 변환
    """

    product_url = get_product_url(review)

    review_id = review.get("review_id")
    product_id = review.get("product_id")
    rating = review.get("rating")
    review_date = review.get("review_date")

    return IncomingReview(
        review_id=str(review_id) if review_id is not None else "",
        product_id=str(product_id) if product_id is not None else None,
        product_url=str(product_url) if product_url is not None else "",
        content=str(review.get("content") or ""),
        user_id=str(review.get("user_id") or "unknown"),
        rating=int(rating) if rating is not None else 0,
        review_date=str(review_date) if review_date is not None else "",
        image_count=int(review.get("image_count") or 0),
        quality_score=review.get("quality_score"),
    )


def calculate_rti(review_dict: dict) -> dict:
    incoming_review = to_incoming_review(review_dict)

    internal_review = prepare_review_input(
        incoming=incoming_review,
        source=review_dict.get("source") or "normalized",
        product_name=review_dict.get("product_name")
    )

    analysis_result = analyze_single_review(internal_review)

    if hasattr(analysis_result, "model_dump"):
        result = analysis_result.model_dump()
    else:
        result = analysis_result

    # main.py 응답에 product_url이 없거나 누락될 경우를 대비해서 보강
    result["product_url"] = get_product_url(review_dict)

    return result
>>>>>>> Stashed changes


def main():
    if not INPUT_PATH.exists():
        print(f"정규화 데이터가 없습니다: {INPUT_PATH}")
        print("먼저 아래 명령어를 실행해주세요:")
        print("python ai/normalizer.py")
        return

    with INPUT_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    reviews = load_reviews(data)

    if not reviews:
        print("분석할 리뷰 데이터가 없습니다.")
        return

<<<<<<< Updated upstream
    # 현재 v0는 normalized 리뷰 배열 전체를 batch로 분석합니다.
=======
>>>>>>> Stashed changes
    results = [calculate_rti(review) for review in reviews]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print(json.dumps(results[:3], ensure_ascii=False, indent=2))
    print(f"\n총 {len(results)}개 리뷰 RTI batch 분석 완료")
<<<<<<< Updated upstream
    print(f"RTI 분석 결과가 저장되었습니다: {OUTPUT_PATH}")
=======
    print(f"결과 저장 완료: {OUTPUT_PATH}")

    missing_product_url_count = sum(
        1 for item in results
        if not item.get("product_url")
    )

    print(f"product_url 누락 개수: {missing_product_url_count}개")
>>>>>>> Stashed changes


if __name__ == "__main__":
    main()