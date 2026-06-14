import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = Path(
    "data/raw/naver_reviews_7195971829_playwright.json"
)
OUTPUT_DIR = Path("output")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze crawled NAVER reviews with the existing RTI logic."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Raw NAVER review JSON (default: {DEFAULT_INPUT_PATH})",
    )
    return parser.parse_args()


def load_raw_data(input_path: Path) -> dict:
    with input_path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Input JSON must contain an object.")
    return data


def load_rti_functions():
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # This validation script must not call the optional GCP sentiment API.
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    try:
        from ai.behavior_analyzer import calculate_behavior_score
        from ai.network_analyzer import calculate_network_score
        from ai.text_analyzer import calculate_text_score
    except ImportError as error:
        missing_name = error.name or "unknown"
        raise RuntimeError(
            f"Failed to import existing RTI module: {missing_name}"
        ) from error
    except Exception as error:
        raise RuntimeError(
            f"Failed to initialize existing RTI modules: {error}"
        ) from error

    return (
        calculate_text_score,
        calculate_behavior_score,
        calculate_network_score,
    )


def normalize_integer(value, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_analysis_input(review: dict) -> dict:
    return {
        "review_id": str(review.get("review_id") or ""),
        "user_id": str(review.get("user_id") or "unknown"),
        "rating": normalize_integer(review.get("rating")),
        "content": str(review.get("content") or ""),
        "review_date": str(review.get("review_date") or "unknown"),
        "image_count": normalize_integer(review.get("image_count")),
        "quality_score": review.get("quality_score"),
        "verified_purchase": review.get(
            "verified_purchase", "unknown"
        ),
        "repurchase": review.get("repurchase", "unknown"),
        "free_trial": review.get("free_trial", "unknown"),
        "reviews_written_today": normalize_integer(
            review.get("reviews_written_today"), default=1
        ),
        "similar_review_count": normalize_integer(
            review.get("similar_review_count")
        ),
    }


def calculate_rti(review: dict, rti_functions: tuple) -> dict:
    (
        calculate_text_score,
        calculate_behavior_score,
        calculate_network_score,
    ) = rti_functions

    analysis_input = build_analysis_input(review)
    text_score, text_reasons = calculate_text_score(
        analysis_input["content"],
        analysis_input["quality_score"],
    )
    behavior_score, behavior_reasons = calculate_behavior_score(
        analysis_input
    )
    network_score, network_reasons = calculate_network_score(
        analysis_input
    )

    rti_score = round(
        text_score * 0.4
        + behavior_score * 0.35
        + network_score * 0.25
    )
    if rti_score < 50:
        level = "danger"
    elif rti_score < 80:
        level = "warn"
    else:
        level = "safe"

    return {
        "review_id": analysis_input["review_id"],
        "user_id": analysis_input["user_id"],
        "rating": analysis_input["rating"],
        "content": analysis_input["content"],
        "review_date": analysis_input["review_date"],
        "rti_score": rti_score,
        "rti": rti_score,
        "level": level,
        "reasons": (
            text_reasons + behavior_reasons + network_reasons
        ),
        "signals": {
            "text": int(text_score),
            "behavior": int(behavior_score),
            "network": int(network_score),
        },
    }


def build_error_result(review: dict, error: Exception) -> dict:
    analysis_input = build_analysis_input(review)
    return {
        "review_id": analysis_input["review_id"],
        "user_id": analysis_input["user_id"],
        "rating": analysis_input["rating"],
        "content": analysis_input["content"],
        "review_date": analysis_input["review_date"],
        "rti_score": None,
        "rti": None,
        "level": "error",
        "reasons": [],
        "signals": {},
        "error": str(error),
    }


def analyze_reviews(
    reviews: list, rti_functions: tuple
) -> tuple[list[dict], int, int]:
    results = []
    analyzed_count = 0
    skipped_count = 0

    for index, review in enumerate(reviews):
        if not isinstance(review, dict):
            print(f"[WARN] Review {index} is not an object. Skipping.")
            skipped_count += 1
            continue

        content = review.get("content")
        if not isinstance(content, str) or not content.strip():
            print(
                f"[WARN] Review {index} has no content. Skipping."
            )
            skipped_count += 1
            continue

        try:
            results.append(calculate_rti(review, rti_functions))
            analyzed_count += 1
        except Exception as error:
            review_id = review.get("review_id", index)
            print(
                f"[WARN] RTI analysis failed for review "
                f"{review_id}: {error}"
            )
            results.append(build_error_result(review, error))
            skipped_count += 1

    return results, analyzed_count, skipped_count


def save_results(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    args = parse_args()
    input_path = args.input_path
    print(f"[INFO] Input file: {input_path.as_posix()}")

    try:
        raw_data = load_raw_data(input_path)
    except FileNotFoundError:
        print(f"[ERROR] Input file not found: {input_path}")
        raise SystemExit(1)
    except json.JSONDecodeError as error:
        print(f"[ERROR] Failed to parse input JSON: {error}")
        raise SystemExit(1)
    except (OSError, ValueError) as error:
        print(f"[ERROR] Failed to read input file: {error}")
        raise SystemExit(1)

    reviews = raw_data.get("reviews")
    if not isinstance(reviews, list):
        print("[ERROR] Input JSON does not contain a reviews array.")
        raise SystemExit(1)
    if not reviews:
        print("[ERROR] Reviews array is empty.")
        raise SystemExit(1)

    product = raw_data.get("product")
    if not isinstance(product, dict):
        product = {}
    product_id = str(product.get("product_id") or "unknown")

    print(f"[INFO] Product ID: {product_id}")
    print(f"[INFO] Reviews loaded: {len(reviews)}")

    try:
        rti_functions = load_rti_functions()
    except RuntimeError as error:
        print(f"[ERROR] {error}")
        raise SystemExit(1)

    results, analyzed_count, skipped_count = analyze_reviews(
        reviews, rti_functions
    )
    output_path = OUTPUT_DIR / f"naver_rti_results_{product_id}.json"
    output_data = {
        "source": raw_data.get("source") or "naver",
        "product": {
            "product_id": product_id,
            "product_name": product.get("product_name", "unknown"),
            "product_url": product.get("product_url", ""),
            "category": product.get("category", "unknown"),
        },
        "review_count": len(reviews),
        "analyzed_count": analyzed_count,
        "skipped_count": skipped_count,
        "results": results,
    }

    try:
        save_results(output_data, output_path)
    except OSError as error:
        print(f"[ERROR] Failed to save RTI results: {error}")
        raise SystemExit(1)

    print(f"[INFO] Reviews analyzed: {analyzed_count}")
    print(f"[INFO] Reviews skipped: {skipped_count}")
    print(f"[INFO] Saved RTI results: {output_path.as_posix()}")


if __name__ == "__main__":
    main()
