import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


OUTPUT_DIR = Path("data/raw")
DEBUG_DIR = Path("data/debug")
GOTO_TIMEOUT_MS = 60_000
JSON_BODY_PREVIEW_LIMIT = 50_000
MAX_REVIEWS = 20
PAGE_KEYWORDS = ("review", "reviews", "구매평", "리뷰", "평점")
NETWORK_KEYWORDS = ("review", "reviews", "contents", "score", "product")
USAGE = (
    "Usage: python scripts/crawl_naver_reviews_playwright.py "
    '"<NAVER_PRODUCT_URL>"'
)


def extract_product_id(product_url: str) -> str:
    parsed_url = urlparse(product_url)
    path_parts = [part for part in parsed_url.path.split("/") if part]

    if "products" in path_parts:
        products_index = path_parts.index("products")
        if products_index + 1 < len(path_parts):
            product_id = path_parts[products_index + 1]
            if product_id.isdigit():
                return product_id

    raise ValueError(f"Could not extract product ID from URL: {product_url}")


def save_json(data: object, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


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


def print_keyword_check(html: str) -> None:
    lowered_html = html.lower()
    results = [
        f"{keyword}={keyword.lower() in lowered_html}"
        for keyword in PAGE_KEYWORDS
    ]
    print(f"[INFO] Keyword check: {', '.join(results)}")


def is_network_candidate(url: str) -> bool:
    lowered_url = url.lower()
    return any(keyword in lowered_url for keyword in NETWORK_KEYWORDS)


def extract_reviews(page) -> list[dict]:
    selectors = (
        '[class*="review" i]',
        '[id*="review" i]',
        '[data-shp-contents-id*="review" i]',
    )
    reviews = []
    seen_texts = set()

    for selector in selectors:
        try:
            texts = page.locator(selector).all_inner_texts()
        except Exception as error:
            print(f"[WARN] Review selector failed ({selector}): {error}")
            continue

        for text in texts:
            normalized_text = " ".join(text.split())
            if (
                len(normalized_text) < 10
                or normalized_text in seen_texts
            ):
                continue

            seen_texts.add(normalized_text)
            reviews.append({"content": normalized_text[:2_000]})
            if len(reviews) >= MAX_REVIEWS:
                return reviews

    return reviews


def crawl_with_playwright(
    sync_playwright, product_url: str, product_id: str
) -> list[dict]:
    html_path = (
        DEBUG_DIR / f"naver_product_{product_id}_playwright.html"
    )
    screenshot_path = (
        DEBUG_DIR / f"naver_product_{product_id}_playwright.png"
    )
    network_path = (
        DEBUG_DIR / f"naver_product_{product_id}_network_candidates.json"
    )
    json_path = (
        DEBUG_DIR / f"naver_product_{product_id}_json_candidates.json"
    )

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    candidate_responses = []
    network_candidates = []
    json_candidates = []
    reviews = []

    try:
        with sync_playwright() as playwright:
            print("[INFO] Opening browser...")
            # Change headless to False when interactive browser debugging is needed.
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            def handle_response(response) -> None:
                if not is_network_candidate(response.url):
                    return

                content_type = response.headers.get(
                    "content-type", "unknown"
                )
                network_candidates.append(
                    {
                        "url": response.url,
                        "status": response.status,
                        "content_type": content_type,
                    }
                )
                if "application/json" in content_type.lower():
                    candidate_responses.append((response, content_type))

            page.on("response", handle_response)

            try:
                page.goto(
                    product_url,
                    wait_until="networkidle",
                    timeout=GOTO_TIMEOUT_MS,
                )
                print("[INFO] Page loaded")
            except Exception as error:
                print(f"[WARN] Page load failed or timed out: {error}")

            try:
                html = page.content()
                html_path.write_text(html, encoding="utf-8")
                print_keyword_check(html)
                print(f"[INFO] Saved debug HTML: {html_path.as_posix()}")
            except Exception as error:
                print(f"[WARN] Failed to save debug HTML: {error}")

            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                print(
                    "[INFO] Saved debug screenshot: "
                    f"{screenshot_path.as_posix()}"
                )
            except Exception as error:
                print(f"[WARN] Failed to save screenshot: {error}")

            reviews = extract_reviews(page)

            for response, content_type in candidate_responses:
                try:
                    body_preview = response.body()[
                        :JSON_BODY_PREVIEW_LIMIT
                    ].decode("utf-8", errors="replace")
                    json_candidates.append(
                        {
                            "url": response.url,
                            "status": response.status,
                            "content_type": content_type,
                            "body_preview": body_preview,
                        }
                    )
                except Exception as error:
                    print(
                        "[WARN] Failed to read JSON response body "
                        f"({response.url}): {error}"
                    )
    except Exception as error:
        print(f"[ERROR] Playwright crawl failed: {error}")
    finally:
        try:
            save_json(network_candidates, network_path)
            print(
                f"[INFO] Network candidates: {len(network_candidates)} "
                f"(saved to {network_path.as_posix()})"
            )
            for candidate in network_candidates:
                print(f"[INFO] Network candidate URL: {candidate['url']}")
        except OSError as error:
            print(f"[ERROR] Failed to save network candidates: {error}")

        try:
            save_json(json_candidates, json_path)
            print(
                f"[INFO] JSON candidates: {len(json_candidates)} "
                f"(saved to {json_path.as_posix()})"
            )
        except OSError as error:
            print(f"[ERROR] Failed to save JSON candidates: {error}")

    return reviews


def import_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] playwright package is required.")
        print("[INFO] Install with:")
        print("pip install playwright")
        print("python -m playwright install chromium")
        return None

    return sync_playwright


def main() -> None:
    if len(sys.argv) != 2:
        print(f"[ERROR] {USAGE}")
        raise SystemExit(1)

    product_url = sys.argv[1]
    print(f"[INFO] Product URL: {product_url}")

    try:
        product_id = extract_product_id(product_url)
    except ValueError as error:
        print(f"[ERROR] {error}")
        raise SystemExit(1) from error

    print(f"[INFO] Product ID: {product_id}")
    reviews = []
    output_path = (
        OUTPUT_DIR / f"naver_reviews_{product_id}_playwright.json"
    )
    sync_playwright = import_playwright()
    if sync_playwright is None:
        raw_result = build_raw_result(product_url, product_id, reviews)
        try:
            save_json(raw_result, output_path)
            print("[INFO] Review count: 0")
            print(f"[INFO] Saved raw JSON: {output_path.as_posix()}")
        except OSError as error:
            print(f"[ERROR] Failed to save raw JSON: {error}")
        raise SystemExit(1)

    try:
        reviews = crawl_with_playwright(
            sync_playwright, product_url, product_id
        )
    finally:
        raw_result = build_raw_result(product_url, product_id, reviews)
        try:
            save_json(raw_result, output_path)
            print(f"[INFO] Review count: {len(reviews)}")
            print(f"[INFO] Saved raw JSON: {output_path.as_posix()}")
        except OSError as error:
            print(f"[ERROR] Failed to save raw JSON: {error}")
            raise SystemExit(1) from error


if __name__ == "__main__":
    main()
