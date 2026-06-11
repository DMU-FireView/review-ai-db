import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


OUTPUT_DIR = Path("data/raw")
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


def fetch_reviews(product_url: str, product_id: str) -> list[dict]:
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
        reviews = fetch_reviews(product_url, product_id)
        raw_result = build_raw_result(product_url, product_id, reviews)
        output_path = OUTPUT_DIR / f"naver_reviews_{product_id}.json"
        save_raw_json(raw_result, output_path)
    except (OSError, ValueError) as error:
        print(f"[ERROR] {error}")
        raise SystemExit(1) from error

    print(f"[INFO] Product ID: {product_id}")
    print(f"[INFO] Review count: {len(reviews)}")
    print(f"[INFO] Saved raw JSON: {output_path.as_posix()}")


if __name__ == "__main__":
    main()
