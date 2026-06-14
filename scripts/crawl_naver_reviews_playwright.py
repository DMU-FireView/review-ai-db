import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


OUTPUT_DIR = Path("data/raw")
DEBUG_DIR = Path("data/debug")
GOTO_TIMEOUT_MS = 60_000
JSON_BODY_PREVIEW_LIMIT = 50_000
REVIEW_API_BODY_PREVIEW_LIMIT = 5_000
REVIEW_API_PARSED_JSON_LIMIT = 1_000_000
MAX_REVIEWS = 20
PAGE_KEYWORDS = (
    "review",
    "reviews",
    "contents",
    "구매평",
    "리뷰",
    "평점",
    "별점",
    "상품평",
)
NETWORK_KEYWORDS = (
    "review",
    "reviews",
    "contents",
    "score",
    "product",
    "comment",
    "evaluation",
    "summary",
)
REVIEW_API_KEYWORDS = (
    "contents/reviews",
    "product-summary",
    "store_pick",
    "review-events",
    "exceptional-storepick-review-ids",
)
REVIEW_TAB_LABELS = ("리뷰", "구매평", "상품평")
MOJIBAKE_MARKERS = (
    "釉",
    "붾",
    "荑",
    "좎",
    "뀡",
    "媛",
    "섎",
    "떎",
    "鍮",
    "쏅",
)
REVIEW_CONTENT_FIELDS = {
    "reviewcontent",
    "content",
    "body",
}
REVIEW_TEXT_FIELDS = ("reviewContent", "content", "body", "text")
REVIEW_RATING_FIELDS = (
    "rating",
    "score",
    "starScore",
    "reviewScore",
    "averageScore",
)
REVIEW_USER_FIELDS = (
    "userId",
    "memberId",
    "writer",
    "nickname",
    "maskedUserId",
    "writerMemberId",
    "maskedWriterId",
)
REVIEW_ID_FIELDS = (
    "id",
    "reviewId",
    "reviewNo",
    "reviewSeq",
    "mallReviewId",
)
REVIEW_DATE_FIELDS = (
    "reviewDate",
    "createdAt",
    "createDate",
    "registerDate",
    "writtenDate",
)
REVIEW_IMAGE_FIELDS = (
    "images",
    "imageUrls",
    "media",
    "attachments",
    "reviewImages",
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


def count_korean_characters(value: str) -> int:
    return sum("\uac00" <= character <= "\ud7a3" for character in value)


def count_korean_signal(value: str) -> int:
    cleaned_value = value
    for marker in MOJIBAKE_MARKERS:
        cleaned_value = cleaned_value.replace(marker, "")
    return count_korean_characters(cleaned_value)


def fix_korean_mojibake(value: str) -> str:
    if not isinstance(value, str):
        return value
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value

    try:
        fixed = value.encode(
            "cp949", errors="ignore"
        ).decode("utf-8", errors="ignore")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return value

    if count_korean_signal(fixed) > count_korean_signal(value):
        return fixed
    return value


def fix_mojibake_in_json(data):
    if isinstance(data, dict):
        return {
            key: fix_mojibake_in_json(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [fix_mojibake_in_json(item) for item in data]
    if isinstance(data, str):
        return fix_korean_mojibake(data)
    return data


def _fix_review_content_fields(review: dict) -> tuple[dict, bool]:
    fixed_review = {}
    content_fixed = False

    for key, value in review.items():
        if isinstance(value, dict):
            fixed_value, nested_fixed = _fix_review_content_fields(value)
            content_fixed = content_fixed or nested_fixed
        elif isinstance(value, list):
            fixed_value = []
            for item in value:
                if isinstance(item, dict):
                    fixed_item, nested_fixed = (
                        _fix_review_content_fields(item)
                    )
                    content_fixed = content_fixed or nested_fixed
                    fixed_value.append(fixed_item)
                else:
                    fixed_value.append(fix_mojibake_in_json(item))
        elif (
            isinstance(value, str)
            and key.lower() in REVIEW_CONTENT_FIELDS
        ):
            fixed_value = fix_korean_mojibake(value)
            content_fixed = content_fixed or fixed_value != value
        else:
            fixed_value = value
        fixed_review[key] = fixed_value

    return fixed_review, content_fixed


def fix_review_content_fields(review: dict) -> dict:
    fixed_review, content_fixed = _fix_review_content_fields(review)
    if content_fixed:
        print("[INFO] Fixed Korean mojibake text in review content.")
    return fixed_review


def first_present_value(data: dict, field_names: tuple[str, ...]):
    for field_name in field_names:
        value = data.get(field_name)
        if value is not None and value != "":
            return value
    return None


def review_item_score(item: dict) -> tuple[int, int, int, int]:
    keys = set(item)
    return (
        int("reviewContent" in keys),
        int(any(field in keys for field in REVIEW_TEXT_FIELDS[1:])),
        int(any(field in keys for field in REVIEW_RATING_FIELDS)),
        int(any(field in keys for field in REVIEW_USER_FIELDS)),
    )


def is_review_like_item(item: dict) -> bool:
    return any(review_item_score(item))


def find_review_like_items(data, path: str = "$") -> list[dict]:
    candidates = []

    if isinstance(data, dict):
        for key, value in data.items():
            candidates.extend(
                find_review_like_items(value, f"{path}.{key}")
            )
    elif isinstance(data, list):
        dict_items = [item for item in data if isinstance(item, dict)]
        review_items = [
            item for item in dict_items if is_review_like_item(item)
        ]
        if review_items:
            sample_keys = sorted(
                {
                    key
                    for item in review_items[:5]
                    for key in item.keys()
                }
            )
            item_scores = [
                review_item_score(item) for item in review_items
            ]
            candidates.append(
                {
                    "path": path,
                    "count": len(review_items),
                    "sample_keys": sample_keys,
                    "items": review_items,
                    "score": tuple(
                        sum(score[index] for score in item_scores)
                        for index in range(4)
                    ),
                }
            )

        for index, item in enumerate(data):
            candidates.extend(
                find_review_like_items(item, f"{path}[{index}]")
            )

    return candidates


def collect_image_urls(value) -> list[str]:
    urls = []

    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            urls.append(value)
    elif isinstance(value, list):
        for item in value:
            urls.extend(collect_image_urls(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            lowered_key = key.lower()
            if (
                "image" in lowered_key
                or "attach" in lowered_key
                or lowered_key in {"url", "path"}
            ):
                urls.extend(collect_image_urls(item))

    return list(dict.fromkeys(urls))


def extract_review_images(review: dict) -> list[str]:
    images = []
    for field_name in REVIEW_IMAGE_FIELDS:
        if field_name in review:
            images.extend(collect_image_urls(review[field_name]))

    for field_name in ("reviewAttach", "repThumbnailAttach"):
        if field_name in review:
            images.extend(collect_image_urls(review[field_name]))

    return list(dict.fromkeys(images))


def normalize_rating(value) -> int | float:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            number = float(value)
            return int(number) if number.is_integer() else number
        except ValueError:
            pass
    return 0


def map_review_items(items: list[dict], product_id: str) -> list[dict]:
    reviews = []

    for index, item in enumerate(items, start=1):
        review_id = first_present_value(item, REVIEW_ID_FIELDS)
        user_id = first_present_value(item, REVIEW_USER_FIELDS)
        rating = first_present_value(item, REVIEW_RATING_FIELDS)
        content = first_present_value(item, REVIEW_TEXT_FIELDS)
        review_date = first_present_value(item, REVIEW_DATE_FIELDS)
        images = extract_review_images(item)

        content_text = content if isinstance(content, str) else ""
        fixed_content = fix_korean_mojibake(content_text)
        if fixed_content != content_text:
            print("[INFO] Fixed Korean mojibake text in review content.")

        reviews.append(
            {
                "review_id": (
                    str(review_id)
                    if review_id is not None
                    else f"naver_{product_id}_{index}"
                ),
                "user_id": (
                    str(user_id) if user_id is not None else "unknown"
                ),
                "rating": normalize_rating(rating),
                "content": fixed_content,
                "review_date": (
                    str(review_date)
                    if review_date is not None
                    else "unknown"
                ),
                "image_count": len(images),
                "images": images,
            }
        )

    return reviews


def analyze_review_api_bodies(
    review_api_bodies: list[dict], product_id: str
) -> tuple[list[dict], list[dict]]:
    debug_candidates = []
    selectable_candidates = []

    for body in review_api_bodies:
        source_url = body.get("url", "unknown")
        for candidate in find_review_like_items(body):
            debug_candidates.append(
                {
                    "source_url": source_url,
                    "path": candidate["path"],
                    "count": candidate["count"],
                    "sample_keys": candidate["sample_keys"],
                }
            )
            selectable_candidates.append(candidate)

    if not selectable_candidates:
        return [], debug_candidates

    best_candidate = max(
        selectable_candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["count"],
        ),
    )
    return (
        map_review_items(best_candidate["items"], product_id),
        debug_candidates,
    )


def build_raw_result(
    product_url: str,
    product_id: str,
    reviews: list[dict],
    crawl_status: dict,
) -> dict:
    crawled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    fixed_reviews = [
        fix_review_content_fields(review)
        for review in reviews
    ]
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
        "reviews": fixed_reviews,
        "crawl_status": crawl_status,
    }


def print_keyword_check(html: str, stage: str) -> None:
    lowered_html = html.lower()
    results = [
        f"{keyword}={keyword.lower() in lowered_html}"
        for keyword in PAGE_KEYWORDS
    ]
    print(f"[INFO] Keyword check {stage}: {', '.join(results)}")


def is_network_candidate(url: str) -> bool:
    lowered_url = url.lower()
    return any(keyword in lowered_url for keyword in NETWORK_KEYWORDS)


def is_review_api(url: str) -> bool:
    lowered_url = url.lower()
    return any(keyword in lowered_url for keyword in REVIEW_API_KEYWORDS)


def is_browser_closed_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "target page, context or browser has been closed" in message
        or "target closed" in message
        or "page has been closed" in message
    )


def log_browser_error(error: Exception, fallback_message: str) -> None:
    if is_browser_closed_error(error):
        print(
            "[WARN] Browser page was closed before review extraction "
            "completed."
        )
    else:
        print(f"{fallback_message}: {error}")


def parse_json_body(body_text: str) -> object | None:
    if len(body_text) > REVIEW_API_PARSED_JSON_LIMIT:
        return None

    try:
        parsed_json = json.loads(body_text)
    except json.JSONDecodeError:
        return None
    return fix_mojibake_in_json(parsed_json)


def scroll_page(page, steps: int = 6, delay_ms: int = 1500) -> None:
    print("[INFO] Scrolling page...")
    for step in range(1, steps + 1):
        try:
            position = page.evaluate(
                """
                () => {
                    const distance = Math.max(window.innerHeight * 0.8, 600);
                    window.scrollBy(0, distance);
                    return {
                        scrollY: Math.round(window.scrollY),
                        scrollHeight: document.body.scrollHeight,
                    };
                }
                """
            )
            print(
                f"[INFO] Scroll step {step}/{steps}: "
                f"scrollY={position['scrollY']}, "
                f"scrollHeight={position['scrollHeight']}"
            )
            page.wait_for_timeout(delay_ms)
        except Exception as error:
            print(f"[WARN] Scroll step {step}/{steps} failed: {error}")


def try_click_review_tab(page, wait_ms: int = 2500) -> bool:
    print("[INFO] Trying to click review tab...")

    for label in REVIEW_TAB_LABELS:
        for exact in (True, False):
            try:
                locator = page.get_by_text(label, exact=exact)
                visible_count = min(locator.count(), 10)
                for index in range(visible_count):
                    candidate = locator.nth(index)
                    if not candidate.is_visible():
                        continue

                    candidate.click(timeout=3000)
                    print(f"[INFO] Clicked review tab: {label}")
                    page.wait_for_timeout(wait_ms)
                    return True
            except Exception as error:
                print(
                    f"[WARN] Review tab click failed "
                    f"({label}, exact={exact}): {error}"
                )

    print("[WARN] No visible review tab was found.")
    return False


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
            if is_browser_closed_error(error):
                log_browser_error(error, "")
                return reviews
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
            fixed_text = fix_korean_mojibake(normalized_text)
            if fixed_text != normalized_text:
                print(
                    "[INFO] Fixed Korean mojibake text in review content."
                )
            reviews.append({"content": fixed_text[:2_000]})
            if len(reviews) >= MAX_REVIEWS:
                return reviews

    return reviews


def crawl_with_playwright(
    sync_playwright,
    product_url: str,
    product_id: str,
    headless: bool,
) -> dict:
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
    review_api_bodies_path = (
        DEBUG_DIR / f"naver_product_{product_id}_review_api_bodies.json"
    )
    review_item_candidates_path = (
        DEBUG_DIR
        / f"naver_product_{product_id}_review_item_candidates.json"
    )

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    network_candidates = []
    json_candidates = []
    review_api_bodies = []
    review_api_bodies_saved = False
    reviews = []

    try:
        with sync_playwright() as playwright:
            print("[INFO] Opening browser...")
            print(f"[INFO] Headless: {headless}")
            browser = playwright.chromium.launch(headless=headless)
            page = browser.new_page()

            def handle_response(response) -> None:
                response_url = response.url
                network_candidate = is_network_candidate(response_url)
                review_api = is_review_api(response_url)
                if not network_candidate and not review_api:
                    return

                content_type = response.headers.get(
                    "content-type", "unknown"
                )
                try:
                    method = response.request.method
                except Exception:
                    method = "unknown"
                metadata = {
                    "url": response_url,
                    "status": response.status,
                    "content_type": content_type,
                    "method": method,
                }
                if network_candidate:
                    network_candidates.append(metadata)

                is_json = "application/json" in content_type.lower()
                if not is_json:
                    if review_api:
                        review_api_bodies.append(
                            {
                                "url": response_url,
                                "status": response.status,
                                "content_type": content_type,
                                "body_preview": "",
                                "json": None,
                            }
                        )
                    return

                try:
                    body_bytes = response.body()
                    body_text = body_bytes.decode(
                        "utf-8", errors="replace"
                    )
                except Exception as error:
                    if review_api:
                        review_api_bodies.append(
                            {
                                "url": response_url,
                                "status": response.status,
                                "content_type": content_type,
                                "body_preview": "",
                                "json": None,
                            }
                        )
                        print(
                            "[WARN] Failed to capture review API body: "
                            f"{response_url} - {error}"
                        )
                    else:
                        print(
                            "[WARN] Failed to read JSON response body "
                            f"({response_url}): {error}"
                        )
                    return

                json_candidates.append(
                    {
                        "url": response_url,
                        "status": response.status,
                        "content_type": content_type,
                        "body_preview": body_text[
                            :JSON_BODY_PREVIEW_LIMIT
                        ],
                    }
                )

                if review_api:
                    review_api_bodies.append(
                        {
                            "url": response_url,
                            "status": response.status,
                            "content_type": content_type,
                            "body_preview": body_text[
                                :REVIEW_API_BODY_PREVIEW_LIMIT
                            ],
                            "json": parse_json_body(body_text),
                        }
                    )
                    print(
                        f"[INFO] Review API body captured: {response_url}"
                    )

            page.on("response", handle_response)

            try:
                page.goto(
                    product_url,
                    wait_until="networkidle",
                    timeout=GOTO_TIMEOUT_MS,
                )
                print("[INFO] Page loaded")
            except Exception as error:
                log_browser_error(
                    error, "[WARN] Page load failed or timed out"
                )

            try:
                initial_html = page.content()
                print_keyword_check(initial_html, "before scroll")
            except Exception as error:
                print(f"[WARN] Failed to inspect initial HTML: {error}")

            scroll_page(page)
            try_click_review_tab(page)

            try:
                final_html = page.content()
                print_keyword_check(final_html, "after scroll")
                html_path.write_text(final_html, encoding="utf-8")
                print(f"[INFO] Saved debug HTML: {html_path.as_posix()}")
            except Exception as error:
                print(f"[WARN] Failed to save final debug HTML: {error}")

            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                print(
                    "[INFO] Saved debug screenshot: "
                    f"{screenshot_path.as_posix()}"
                )
            except Exception as error:
                print(f"[WARN] Failed to save screenshot: {error}")

            reviews = extract_reviews(page)

            try:
                save_json(review_api_bodies, review_api_bodies_path)
                review_api_bodies_saved = True
                print(
                    f"[INFO] Review API bodies: {len(review_api_bodies)} "
                    f"(saved to {review_api_bodies_path.as_posix()})"
                )
            except OSError as error:
                print(
                    "[ERROR] Failed to save review API bodies before "
                    f"browser close: {error}"
                )
    except Exception as error:
        log_browser_error(error, "[ERROR] Playwright crawl failed")
    finally:
        api_reviews, review_item_candidates = analyze_review_api_bodies(
            review_api_bodies, product_id
        )
        if api_reviews:
            reviews = api_reviews

        if not review_api_bodies_saved:
            try:
                save_json(review_api_bodies, review_api_bodies_path)
                print(
                    f"[INFO] Review API bodies: {len(review_api_bodies)} "
                    f"(saved to {review_api_bodies_path.as_posix()})"
                )
            except OSError as error:
                print(f"[ERROR] Failed to save review API bodies: {error}")

        try:
            save_json(
                review_item_candidates,
                review_item_candidates_path,
            )
            print(
                "[INFO] Review item candidates: "
                f"{len(review_item_candidates)} "
                f"(saved to {review_item_candidates_path.as_posix()})"
            )
        except OSError as error:
            print(f"[ERROR] Failed to save review item candidates: {error}")

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

    return {
        "reviews": reviews,
        "review_api_body_count": len(review_api_bodies),
        "network_candidate_count": len(network_candidates),
        "json_candidate_count": len(json_candidates),
        "review_json_candidate_count": sum(
            is_review_api(candidate["url"])
            for candidate in json_candidates
        ),
    }


def build_crawl_status(crawl_result: dict) -> dict:
    review_count = len(crawl_result["reviews"])
    review_api_body_count = crawl_result["review_api_body_count"]
    network_candidate_count = crawl_result["network_candidate_count"]
    success = review_count > 0

    if success:
        message = "reviews extracted"
    elif review_api_body_count > 0:
        message = "review API responses captured; no reviews extracted"
    else:
        message = "no review API responses captured"

    return {
        "success": success,
        "review_count": review_count,
        "review_api_body_count": review_api_body_count,
        "network_candidate_count": network_candidate_count,
        "message": message,
    }


def save_raw_result(
    product_url: str,
    product_id: str,
    crawl_result: dict,
    output_path: Path,
    empty_output_path: Path,
) -> Path:
    reviews = crawl_result["reviews"]
    crawl_status = build_crawl_status(crawl_result)
    raw_result = build_raw_result(
        product_url,
        product_id,
        reviews,
        crawl_status,
    )

    if reviews:
        save_json(raw_result, output_path)
        print(f"[INFO] Saved raw JSON: {output_path.as_posix()}")
        return output_path

    if output_path.exists():
        print(
            "[WARN] Review count is 0. Existing successful raw JSON "
            "will not be overwritten."
        )
    else:
        print(
            "[WARN] Review count is 0. Successful raw JSON will not "
            "be created."
        )

    save_json(raw_result, empty_output_path)
    print(
        f"[INFO] Saved empty raw JSON: {empty_output_path.as_posix()}"
    )
    return empty_output_path


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


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a NAVER product page with Playwright."
    )
    parser.add_argument("product_url", help="NAVER product URL")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the Chromium browser window.",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    product_url = args.product_url
    headless = not args.headed
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
    empty_output_path = (
        OUTPUT_DIR / f"naver_reviews_{product_id}_playwright_empty.json"
    )
    empty_crawl_result = {
        "reviews": reviews,
        "review_api_body_count": 0,
        "network_candidate_count": 0,
        "json_candidate_count": 0,
        "review_json_candidate_count": 0,
    }
    sync_playwright = import_playwright()
    if sync_playwright is None:
        try:
            print("[INFO] Review count: 0")
            save_raw_result(
                product_url,
                product_id,
                empty_crawl_result,
                output_path,
                empty_output_path,
            )
        except OSError as error:
            print(f"[ERROR] Failed to save raw JSON: {error}")
        raise SystemExit(1)

    try:
        crawl_result = crawl_with_playwright(
            sync_playwright,
            product_url,
            product_id,
            headless=headless,
        )
    except Exception as error:
        log_browser_error(error, "[ERROR] Playwright crawl failed")
        crawl_result = empty_crawl_result

    try:
        print(f"[INFO] Review count: {len(crawl_result['reviews'])}")
        save_raw_result(
            product_url,
            product_id,
            crawl_result,
            output_path,
            empty_output_path,
        )
    except OSError as error:
        print(f"[ERROR] Failed to save raw JSON: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
