"""팀원별 원본 리뷰 데이터를 공통 입력 형식으로 변환한다."""

import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BIN_INPUT_PATH = Path("data/raw/bin_reviews.json")
HAYEON_INPUT_PATH = Path("data/raw/hayeon_reviews.json")
NORMALIZED_INPUT_PATH = Path("data/normalized/reviews.json")
OUTPUT_DIR = Path("data/converted/products")


def load_reviews_from_json(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Skip missing file: {path}")
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("reviews", "data", "items", "results"):
            if isinstance(data.get(key), list):
                return data[key]

    return []


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def first_value(*values, default=None):
    for value in values:
        if value not in (None, ""):
            return value
    return default


def extract_product_id_from_url(url: str | None) -> str | None:
    if not url:
        return None

    parsed = urlparse(url)

    # SmartStore 예:
    # https://smartstore.naver.com/main/products/7195971829
    parts = [part for part in parsed.path.split("/") if part]
    if "products" in parts:
        idx = parts.index("products")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    # 일반 쇼핑몰 예:
    # ?product_no=6564
    query = parse_qs(parsed.query)
    if query.get("product_no"):
        return query["product_no"][0]

    return None


def normalize_category(raw_category: str | None, product_name: str | None = None) -> str:
    """
    v1 초안에서는 products.category에 대분류를 저장합니다.
    """
    text = f"{raw_category or ''} {product_name or ''}"

    if any(keyword in text for keyword in [
        "이어폰", "헤드폰", "스피커", "TV", "노트북", "모니터",
        "스마트폰", "태블릿", "가전", "전자"
    ]):
        return "디지털/가전"

    if any(keyword in text for keyword in [
        "신발", "스니커즈", "나이키", "에어맥스", "구두", "샌들", "부츠", "슬리퍼"
    ]):
        return "패션잡화"

    if any(keyword in text for keyword in [
        "의류", "티셔츠", "팬츠", "원피스", "니트", "아우터", "셔츠"
    ]):
        return "패션의류"

    if any(keyword in text for keyword in [
        "쿠션", "립", "크림", "스킨", "토너", "클렌징", "샴푸", "바디", "뷰티"
    ]):
        return "뷰티"

    if any(keyword in text for keyword in [
        "과자", "음료", "커피", "유산균", "홍삼", "단백질", "식품"
    ]):
        return "식품"

    return raw_category or "미분류"


def get_product_url(raw: dict) -> str | None:
    return first_value(
        raw.get("product_url"),
        raw.get("productUrl"),
        raw.get("page_url"),
        raw.get("url"),
    )


def get_product_id(raw: dict, product_url: str | None) -> str:
    product_id = first_value(
        raw.get("product_id"),
        raw.get("productId"),
        raw.get("productNo"),
        raw.get("product_no"),
        extract_product_id_from_url(product_url),
        default="unknown_product",
    )

    return str(product_id)


def normalize_review(raw: dict, source: str) -> dict:
    product_url = get_product_url(raw)
    product_id = get_product_id(raw, product_url)

    product_name = first_value(
        raw.get("product_name"),
        raw.get("productName"),
        raw.get("name"),
        raw.get("productTitle"),
        default="상품명 없음",
    )

    raw_category = first_value(
        raw.get("category"),
        raw.get("categoryDisplayName"),
        raw.get("category_name"),
    )

    category = normalize_category(raw_category, product_name)

    review_id = first_value(
        raw.get("review_id"),
        raw.get("reviewId"),
        raw.get("id"),
        raw.get("reviewNo"),
    )

    user_id = first_value(
        raw.get("user_id"),
        raw.get("userId"),
        raw.get("author"),
        raw.get("writer"),
        raw.get("nickname"),
        default="unknown",
    )

    rating = first_value(
        raw.get("rating"),
        raw.get("score"),
        raw.get("star"),
        default=0,
    )

    content = first_value(
        raw.get("content"),
        raw.get("reviewContent"),
        raw.get("text"),
        raw.get("body"),
        default="",
    )

    review_date = first_value(
        raw.get("review_date"),
        raw.get("reviewDate"),
        raw.get("date"),
        raw.get("created_at"),
        default="1970-01-01",
    )

    verified_purchase = first_value(
        raw.get("verified_purchase"),
        raw.get("verifiedPurchase"),
        default=False,
    )

    reviews_written_today = first_value(
        raw.get("reviews_written_today"),
        raw.get("reviewsWrittenToday"),
        default=1,
    )

    similar_review_count = first_value(
        raw.get("similar_review_count"),
        raw.get("similarReviewCount"),
        default=0,
    )

    return {
        "source": source,
        "product": {
            "product_id": product_id,
            "product_name": product_name,
            "product_url": product_url,
            "category": category,
        },
        "review": {
            "review_id": str(review_id or ""),
            "user_id": str(user_id),
            "rating": int(float(rating or 0)),
            "content": content,
            "review_date": str(review_date)[:10],
            "verified_purchase": bool(verified_purchase),
            "account_age_days": raw.get("account_age_days"),
            "reviews_written_today": int(reviews_written_today or 1),
            "similar_review_count": int(similar_review_count or 0),
        },
    }


def merge_reviews(sources: list[tuple[str, list[dict]]]) -> dict:
    products = {}
    grouped_reviews = defaultdict(dict)

    for source_name, reviews in sources:
        for raw in reviews:
            normalized = normalize_review(raw, source_name)

            product = normalized["product"]
            review = normalized["review"]

            product_id = product["product_id"]
            review_id = review["review_id"]

            if product_id == "unknown_product":
                continue

            if not review_id or not review["content"]:
                continue

            products[product_id] = product

            # review_id 기준 중복 제거
            if review_id not in grouped_reviews[product_id]:
                grouped_reviews[product_id][review_id] = review

    return {
        product_id: {
            "product": products[product_id],
            "reviews": list(grouped_reviews[product_id].values()),
        }
        for product_id in grouped_reviews
    }


def main() -> None:
    bin_reviews = load_reviews_from_json(BIN_INPUT_PATH)
    hayeon_reviews = load_reviews_from_json(HAYEON_INPUT_PATH)
    normalized_reviews = load_reviews_from_json(NORMALIZED_INPUT_PATH)

    merged = merge_reviews(
        [
            ("bin", bin_reviews),
            ("hayeon", hayeon_reviews),
            ("normalized", normalized_reviews),
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for product_id, data in merged.items():
        save_json(OUTPUT_DIR / f"{product_id}.json", data)

    print("Raw review conversion completed.")
    print(f"bin review count: {len(bin_reviews)}")
    print(f"hayeon review count: {len(hayeon_reviews)}")
    print(f"normalized review count: {len(normalized_reviews)}")
    print(f"product count: {len(merged)}")
    print(f"output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
