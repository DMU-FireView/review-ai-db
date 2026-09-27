"""정규화된 리뷰를 일괄 분석해 RTI 결과 JSON을 생성한다."""
import json
from pathlib import Path

# main.py의 Clean Payload 구조와 분석 엔진을 그대로 사용
from main import IncomingReview, prepare_review_input, analyze_single_review


INPUT_PATH = Path("data/normalized/reviews.json")
OUTPUT_PATH = Path("output/rti_results.json")


def load_reviews(data):
    """
    data/normalized/reviews.json 구조가
    배열이든, {"reviews": [...]} 형태든 처리합니다.
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
    정규화된 리뷰 1개를 main.py의 IncomingReview 구조로 변환합니다.
    숫자로 들어온 review_id/product_id도 문자열로 변환합니다.
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
    """
    main.py의 analyze_single_review를 사용해 RTI를 계산하고,
    원본 정규화 데이터의 메타정보를 다시 붙여 rti_results.json 형태로 저장합니다.
    """

    incoming_review = to_incoming_review(review_dict)

    internal_review = prepare_review_input(
        incoming=incoming_review,
        source=review_dict.get("source") or "normalized",
        product_name=review_dict.get("product_name")
    )

    analysis_result = analyze_single_review(internal_review)

    if hasattr(analysis_result, "model_dump"):
        analysis_result = analysis_result.model_dump()

    product_url = get_product_url(review_dict)

    return {
        "source": review_dict.get("source"),
        "review_id": str(review_dict.get("review_id")) if review_dict.get("review_id") is not None else None,
        "user_id": review_dict.get("user_id"),
        "product_id": str(review_dict.get("product_id")) if review_dict.get("product_id") is not None else None,
        "product_url": product_url,
        "product_name": review_dict.get("product_name"),
        "rating": review_dict.get("rating"),
        "review_date": review_dict.get("review_date"),

        "rti": analysis_result.get("rti"),
        "level": analysis_result.get("level"),

        "signals": analysis_result.get("signals", {}),
        "input_features": analysis_result.get("input_features", {
            "image_count": review_dict.get("image_count", 0),
            "quality_score": review_dict.get("quality_score"),
            "verified_purchase": review_dict.get("verified_purchase", "unknown"),
            "repurchase": review_dict.get("repurchase", "unknown"),
            "free_trial": review_dict.get("free_trial", "unknown"),
            "reviews_written_today": review_dict.get("reviews_written_today", 1),
            "similar_review_count": review_dict.get("similar_review_count", 0)
        }),
        "reasons": analysis_result.get("reasons", [])
    }


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

    results = [calculate_rti(review) for review in reviews]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print(json.dumps(results[:3], ensure_ascii=False, indent=2))
    print(f"\n총 {len(results)}개 리뷰 RTI batch 분석 완료")
    print(f"결과 저장 완료: {OUTPUT_PATH}")

    missing_product_url_count = sum(
        1 for item in results
        if not item.get("product_url")
    )

    print(f"product_url 누락 개수: {missing_product_url_count}개")


if __name__ == "__main__":
    main()
