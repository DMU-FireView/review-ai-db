"""HTTP 요청으로 네이버 상품 리뷰 데이터를 수집하는 보조 크롤러이다."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


OUTPUT_DIR = Path("data/raw")
DEBUG_DIR = Path("data/debug")
DEBUG_CONTENT_LIMIT = 200_000
REQUEST_TIMEOUT_SECONDS = 15
REVIEW_KEYWORDS = ("review", "reviews", "contents", "평점", "구매평")
USAGE = 'Usage: python scripts/crawl_naver_reviews.py "<NAVER_PRODUCT_URL>"'


def extract_product_id(product_url: str) -> str:
    parsed_url = urlparse(product_url)
    path_parts = [part for part in parsed_url.path.split("/") if part]

    if "products" in path_parts:
        products_index = path_parts.index("products")
        if products_index + 1 < len(path_parts):
            product_id = path_parts[products_index + 1]
            if product_id.isdigit():
                return product_id

    if path_parts and path_parts[-1].isdigit():
        return path_parts[-1]

    raise ValueError(f"Could not extract product ID from URL: {product_url}")


def save_debug_response(content: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        content[:DEBUG_CONTENT_LIMIT],
        encoding="utf-8",
    )
    print(f"[INFO] Response saved to: {output_path.as_posix()}")


def print_keyword_check(response_text: str) -> None:
    lowered_text = response_text.lower()
    results = [
        f"{keyword}={keyword.lower() in lowered_text}"
        for keyword in REVIEW_KEYWORDS
    ]
    print(f"[INFO] Keyword check: {', '.join(results)}")


def extract_reviews_from_json(response_data: object) -> list[dict]:
    if not isinstance(response_data, dict):
        return []

    for key in ("reviews", "contents"):
        value = response_data.get(key)
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value

    return []


def fetch_reviews(product_url: str, product_id: str) -> list[dict]:
    try:
        import requests
    except ImportError:
        print(
            "[ERROR] requests package is required. "
            "Please install it with: pip install requests"
        )
        return []

    headers = {
        "accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "application/json;q=0.8,*/*;q=0.7"
        ),
        "user-agent": "Mozilla/5.0",
        "referer": product_url,
    }

    try:
        response = requests.get(
            product_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        print(
            f"[ERROR] Request timed out after {REQUEST_TIMEOUT_SECONDS} seconds."
        )
        return []
    except requests.RequestException as error:
        print(f"[ERROR] Network request failed: {error}")
        return []

    content_type = response.headers.get("content-type", "unknown")
    response_text = response.text
    normalized_content_type = content_type.lower()
    stripped_response = response_text.lstrip()
    is_json = (
        "json" in normalized_content_type
        or stripped_response.startswith(("{", "["))
    )

    print(f"[INFO] HTTP status: {response.status_code}")
    print(f"[INFO] Content-Type: {content_type}")
    print_keyword_check(response_text)

    debug_extension = "json" if is_json else "html"
    debug_path = DEBUG_DIR / f"naver_product_{product_id}.{debug_extension}"

    try:
        save_debug_response(response_text, debug_path)
    except OSError as error:
        print(f"[ERROR] Failed to save debug response: {error}")

    if response.status_code != 200:
        print(f"[WARN] HTTP request returned status {response.status_code}.")
        return []

    if is_json:
        try:
            response_data = response.json()
        except ValueError as error:
            print(f"[ERROR] Failed to decode JSON response: {error}")
            return []

        if isinstance(response_data, dict):
            keys = list(response_data.keys())[:10]
            print(f"[INFO] JSON top-level keys: {keys}")
        elif isinstance(response_data, list):
            print(f"[INFO] JSON top-level list length: {len(response_data)}")
        else:
            print(
                "[INFO] JSON top-level type: "
                f"{type(response_data).__name__}"
            )

        reviews = extract_reviews_from_json(response_data)
        if reviews:
            print(f"[INFO] Extracted reviews from JSON: {len(reviews)}")
            return reviews

    print(
        "[WARN] Review extraction is not implemented "
        "for this response format yet."
    )
    return []


def build_raw_result(
    product_url: str, product_id: str, reviews: list[dict]
) -> dict:
    crawled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "source": "naver",
        "mall": "NAVER",
        "crawled_at": crawled_at,
        "product": {
            "product_id": product_id,
            "product_name": "unknown",
            "product_url": product_url,
            "category": "unknown",
        },
        "reviews": reviews,
    }


def save_raw_json(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    if len(sys.argv) != 2:
        print(f"[ERROR] {USAGE}")
        raise SystemExit(1)

    product_url = sys.argv[1]
    print(f"[INFO] Product URL: {product_url}")

    try:
        product_id = extract_product_id(product_url)
        print(f"[INFO] Product ID: {product_id}")
        reviews = fetch_reviews(product_url, product_id)
        raw_result = build_raw_result(product_url, product_id, reviews)
        output_path = OUTPUT_DIR / f"naver_reviews_{product_id}.json"
        save_raw_json(raw_result, output_path)
    except (OSError, ValueError) as error:
        print(f"[ERROR] {error}")
        raise SystemExit(1) from error

    print(f"[INFO] Review count: {len(reviews)}")
    print(f"[INFO] Saved raw JSON: {output_path.as_posix()}")


if __name__ == "__main__":
    main()
