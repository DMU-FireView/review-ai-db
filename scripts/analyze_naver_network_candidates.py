import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


OUTPUT_DIR = Path("data/debug")
REVIEW_KEYWORDS = (
    "contents/reviews",
    "product-summary",
    "store_pick",
    "review-events",
    "review",
    "reviews",
)
PARAMETER_NAMES = (
    "originProductNo",
    "channelProductNo",
    "productId",
    "checkoutMerchantNo",
    "leafCategoryId",
    "category1Id",
    "category2Id",
    "category3Id",
    "searchSortType",
    "page",
    "pageSize",
)
USAGE = (
    "Usage: python scripts/analyze_naver_network_candidates.py "
    '"<NETWORK_CANDIDATES_JSON>"'
)


def load_candidates(input_path: Path) -> list[dict]:
    with input_path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Network candidates JSON must contain an array.")

    candidates = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            print(f"[WARN] Skipping non-object candidate at index {index}.")
            continue
        candidates.append(item)

    return candidates


def is_review_related(candidate: dict) -> bool:
    url = candidate.get("url")
    if not isinstance(url, str):
        return False

    lowered_path = urlparse(url).path.lower()
    return any(keyword in lowered_path for keyword in REVIEW_KEYWORDS)


def first_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if not values:
        return None
    return values[0]


def extract_origin_product_no(path: str) -> str | None:
    patterns = (
        r"/contents/reviews/product-summary/(\d+)",
        r"/contents/reviews/(\d+)",
        r"/review-events/by-original-product/(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, path, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_parameters(url: str) -> dict[str, str]:
    parsed_url = urlparse(url)
    query = parse_qs(parsed_url.query, keep_blank_values=True)
    extracted = {}

    for name in PARAMETER_NAMES:
        value = first_query_value(query, name)
        if value is not None:
            extracted[name] = value

    if "originProductNo" not in extracted:
        origin_product_no = extract_origin_product_no(parsed_url.path)
        if origin_product_no is not None:
            extracted["originProductNo"] = origin_product_no

    return extracted


def analyze_candidate(candidate: dict) -> dict:
    url = candidate.get("url", "")
    return {
        "url": url,
        "status": candidate.get("status", "unknown"),
        "content_type": candidate.get("content_type", "unknown"),
        "method": candidate.get("method", "unknown"),
        "extracted": extract_parameters(url),
    }


def extract_product_id(input_path: Path) -> str:
    match = re.search(
        r"naver_product_(\d+)_network_candidates\.json$",
        input_path.name,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return "unknown"


def print_analysis(candidates: list[dict], total_count: int) -> None:
    print(f"[INFO] Total candidates: {total_count}")
    print(f"[INFO] Review-related candidates: {len(candidates)}")

    for index, candidate in enumerate(candidates, start=1):
        print()
        print(f"[REVIEW API CANDIDATE {index}]")
        print(f"URL: {candidate['url']}")
        print(f"Status: {candidate['status']}")
        print(f"Content-Type: {candidate['content_type']}")
        print(f"Method: {candidate['method']}")
        print("Extracted:")
        if candidate["extracted"]:
            for name in PARAMETER_NAMES:
                if name in candidate["extracted"]:
                    print(f"  {name}: {candidate['extracted'][name]}")
        else:
            print("  (none)")


def main() -> None:
    if len(sys.argv) != 2:
        print(USAGE)
        raise SystemExit(1)

    input_path = Path(sys.argv[1])

    try:
        candidates = load_candidates(input_path)
    except FileNotFoundError:
        print(f"[ERROR] Input file not found: {input_path}")
        raise SystemExit(1)
    except json.JSONDecodeError as error:
        print(f"[ERROR] Invalid JSON: {error}")
        raise SystemExit(1)
    except (OSError, ValueError) as error:
        print(f"[ERROR] Failed to read input file: {error}")
        raise SystemExit(1)

    review_candidates = [
        analyze_candidate(candidate)
        for candidate in candidates
        if is_review_related(candidate)
    ]
    print_analysis(review_candidates, len(candidates))

    product_id = extract_product_id(input_path)
    output_path = (
        OUTPUT_DIR / f"naver_review_api_candidates_{product_id}.json"
    )
    result = {
        "source_file": input_path.as_posix(),
        "total_candidates": len(candidates),
        "review_related_count": len(review_candidates),
        "candidates": review_candidates,
    }

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
            file.write("\n")
    except OSError as error:
        print(f"[ERROR] Failed to save analysis result: {error}")
        raise SystemExit(1)

    print()
    print(f"[INFO] Saved analysis: {output_path.as_posix()}")


if __name__ == "__main__":
    main()
