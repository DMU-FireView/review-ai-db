import json
import re
from pathlib import Path


RAW_DIR = Path("data/raw")
NORMALIZED_DIR = Path("data/normalized")
OUTPUT_PATH = NORMALIZED_DIR / "reviews.json"


def load_json_file(path):
    with path.open("r", encoding="utf-8") as file:
        text = file.read()

    # 배열/객체 마지막에 붙은 쉼표 자동 제거
    # 예: [1, 2, ] -> [1, 2]
    # 예: {"a": 1, } -> {"a": 1}
    text = re.sub(r",\s*([\]}])", r"\1", text)

    return json.loads(text)


def save_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def clean_html_text(value):
    if value is None:
        return None

    text = str(value)

    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", "", text)

    # HTML 엔티티 정리
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    return text.strip()


def normalize_bin_review_data(data):
    """
    빈님 방식 데이터 변환
    data/raw/bin_reviews.json 기준
    """

    product = data.get("product", {})
    crawl_result = data.get("crawl_result", {})
    reviews = crawl_result.get("reviews", [])

    normalized_reviews = []

    for review in reviews:
        raw = review.get("raw", {})

        normalized_reviews.append({
            "source": "bin",
            "review_id": review.get("review_id") or raw.get("id"),
            "product_id": review.get("product_id") or product.get("productId"),
            "product_name": clean_html_text(product.get("title")),
            "product_url": product.get("link") or review.get("page_url"),
            "user_id": review.get("author") or raw.get("userId"),
            "rating": review.get("rating") or raw.get("starScore"),
            "content": review.get("content") or raw.get("content"),
            "review_date": review.get("review_date") or raw.get("registerDate"),
            "image_count": review.get("image_count") or raw.get("imageCount") or 0,
            "images": review.get("images") or raw.get("images") or [],
            "video_count": raw.get("videoCount", 0),
            "quality_score": review.get("quality_score") or raw.get("qualityScore"),
            "topics": review.get("topics") or raw.get("topics") or [],

            "verified_purchase": "unknown",
            "repurchase": "unknown",
            "free_trial": "unknown",
            "account_age_days": None,

            "reviews_written_today": None,
            "similar_review_count": 0
        })

    return normalized_reviews


def normalize_hayeon_review_data(data):
    """
    하연 방식 데이터 변환
    data/raw/hayeon_reviews.txt 기준
    """

    contents = data.get("contents", [])
    normalized_reviews = []

    for review in contents:
        attaches = review.get("reviewAttaches", [])
        product_order_no = review.get("productOrderNo")

        normalized_reviews.append({
            "source": "hayeon",
            "review_id": review.get("id"),
            "product_id": review.get("productNo") or review.get("knowledgeShoppingMallProductId"),
            "product_name": clean_html_text(review.get("productName")),
            "product_url": review.get("productUrl"),
            "user_id": review.get("maskedWriterId") or review.get("writerId"),
            "rating": review.get("reviewScore"),
            "content": review.get("reviewContent"),
            "review_date": review.get("createDate"),
            "image_count": len(attaches),
            "images": [
                attach.get("attachUrl")
                for attach in attaches
                if attach.get("attachUrl")
            ],
            "video_count": 0,
            "quality_score": None,
            "topics": review.get("reviewContentAnalysisSummaryTags", []),

            "verified_purchase": True if product_order_no else "unknown",
            "repurchase": review.get("repurchase", "unknown"),
            "free_trial": review.get("freeTrial", "unknown"),
            "account_age_days": None,

            "reviews_written_today": None,
            "similar_review_count": 0,

            "review_type": review.get("reviewType"),
            "review_content_class_type": review.get("reviewContentClassType"),
            "help_count": review.get("helpCount", 0),
            "product_option": review.get("productOptionContent"),
            "user_info_values": review.get("reviewUserInfoValues", [])
        })

    return normalized_reviews


def calculate_reviews_written_today(reviews):
    """
    같은 작성자가 같은 날짜에 작성한 리뷰 수 계산
    """

    count_map = {}

    for review in reviews:
        user_id = review.get("user_id")
        review_date = str(review.get("review_date") or "")[:10]

        if not user_id or not review_date:
            continue

        key = f"{user_id}_{review_date}"
        count_map[key] = count_map.get(key, 0) + 1

    for review in reviews:
        user_id = review.get("user_id")
        review_date = str(review.get("review_date") or "")[:10]
        key = f"{user_id}_{review_date}"

        review["reviews_written_today"] = count_map.get(key, 1)

    return reviews


def calculate_similar_review_count(reviews):
    """
    v0용 간단 유사 리뷰 개수 계산
    """

    contents = []

    for review in reviews:
        content = (review.get("content") or "").replace(" ", "").replace("\n", "")
        contents.append(content)

    for index, review in enumerate(reviews):
        current = contents[index]

        if not current:
            review["similar_review_count"] = 0
            continue

        similar_count = 0

        for other_index, other in enumerate(contents):
            if index == other_index or not other:
                continue

            if current == other:
                similar_count += 1

        review["similar_review_count"] = similar_count

    return reviews


def normalize_all():
    all_reviews = []

    bin_path = RAW_DIR / "bin_reviews.json"
    hayeon_path = RAW_DIR / "hayeon_reviews.txt"

    if bin_path.exists():
        bin_data = load_json_file(bin_path)
        all_reviews.extend(normalize_bin_review_data(bin_data))
        print(f"빈님 데이터 변환 완료: {bin_path}")

    if hayeon_path.exists():
        hayeon_data = load_json_file(hayeon_path)
        all_reviews.extend(normalize_hayeon_review_data(hayeon_data))
        print(f"하연 데이터 변환 완료: {hayeon_path}")

    if not all_reviews:
        print("변환할 원본 데이터가 없습니다.")
        print("data/raw/bin_reviews.json 또는 data/raw/hayeon_reviews.txt 파일을 넣어주세요.")
        return []

    all_reviews = calculate_reviews_written_today(all_reviews)
    all_reviews = calculate_similar_review_count(all_reviews)

    save_json_file(OUTPUT_PATH, all_reviews)

    print(f"정규화 완료: {OUTPUT_PATH}")
    print(f"총 리뷰 수: {len(all_reviews)}개")

    return all_reviews


if __name__ == "__main__":
    normalize_all()