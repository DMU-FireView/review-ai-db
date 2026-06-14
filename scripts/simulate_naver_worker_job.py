"""Simulate the future FastAPI Queue Worker flow locally.

This script is a local simulation of the future FastAPI Queue Worker flow.
It does not connect to Redis, DB, Spring, or external APIs.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "output"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.crawl_naver_reviews_playwright import extract_product_id


def relative_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def save_json(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_json_object(input_path: Path) -> dict:
    with input_path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


def load_review_count(input_path: Path) -> int:
    data = load_json_object(input_path)
    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        raise ValueError("JSON does not contain a reviews array")
    if not reviews:
        raise ValueError("reviews array is empty")
    return len(reviews)


def build_summary(product_id: str, product_url: str) -> dict:
    return {
        "job_id": f"local-{product_id}",
        "platform": "NAVER",
        "product_id": product_id,
        "product_url": product_url,
        "status": "RUNNING",
        "used_fallback_raw_json": False,
        "steps": [],
        "message": "local worker simulation started",
    }


def save_summary(summary: dict, summary_path: Path) -> None:
    save_json(summary, summary_path)
    print(f"[INFO] Saved job summary: {relative_path(summary_path)}")


def fail_job(
    summary: dict,
    summary_path: Path,
    message: str,
    step: dict | None = None,
) -> int:
    if step is not None:
        summary["steps"].append(step)
    summary["status"] = "FAILED"
    summary["message"] = message
    save_summary(summary, summary_path)
    print(f"[ERROR] Local worker job failed: {message}")
    return 1


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate a NAVER worker job locally."
    )
    parser.add_argument("product_url", help="NAVER product URL")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the Playwright crawler with a visible browser.",
    )
    return parser.parse_args(argv)


def run_script(
    script_path: Path,
    argument: str,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    command = [sys.executable, str(script_path), argument]
    if extra_args:
        command.extend(extra_args)

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    )


def main() -> int:
    args = parse_args()
    product_url = args.product_url
    print("[INFO] Local worker job started")
    print(f"[INFO] Product URL: {product_url}")

    try:
        product_id = extract_product_id(product_url)
    except ValueError as error:
        print(f"[ERROR] Local worker job failed: {error}")
        return 1

    print(f"[INFO] Product ID: {product_id}")

    raw_path = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / f"naver_reviews_{product_id}_playwright.json"
    )
    empty_raw_path = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / f"naver_reviews_{product_id}_playwright_empty.json"
    )
    rti_path = OUTPUT_DIR / f"naver_rti_results_{product_id}.json"
    summary_path = OUTPUT_DIR / f"naver_worker_job_{product_id}.json"
    summary = build_summary(product_id, product_url)

    crawler_script = (
        PROJECT_ROOT / "scripts" / "crawl_naver_reviews_playwright.py"
    )
    raw_signature_before = file_signature(raw_path)
    empty_raw_signature_before = file_signature(empty_raw_path)
    fallback_review_count = None
    try:
        fallback_review_count = load_review_count(raw_path)
    except (OSError, json.JSONDecodeError, ValueError):
        pass

    print(f"[INFO] Crawler headed mode: {args.headed}")
    print("[INFO] Running crawler...")
    crawler_result = None
    crawler_start_error = None
    try:
        crawler_extra_args = ["--headed"] if args.headed else None
        crawler_result = run_script(
            crawler_script,
            product_url,
            crawler_extra_args,
        )
    except OSError as error:
        crawler_start_error = error

    raw_signature_after = file_signature(raw_path)
    empty_raw_updated = (
        file_signature(empty_raw_path) != empty_raw_signature_before
    )
    crawler_succeeded = (
        crawler_result is not None and crawler_result.returncode == 0
    )
    raw_updated = (
        raw_signature_after is not None
        and raw_signature_after != raw_signature_before
    )

    review_count = None
    if crawler_succeeded and raw_updated and not empty_raw_updated:
        try:
            review_count = load_review_count(raw_path)
        except (OSError, json.JSONDecodeError, ValueError):
            review_count = None

    used_fallback = review_count is None
    if used_fallback:
        print("[WARN] Crawler did not extract reviews in this run.")
        print(
            "[INFO] Checking fallback raw JSON: "
            f"{relative_path(raw_path)}"
        )

        current_fallback_review_count = None
        if fallback_review_count is not None:
            try:
                current_fallback_review_count = load_review_count(raw_path)
            except (OSError, json.JSONDecodeError, ValueError):
                pass

        if current_fallback_review_count is None:
            print("[ERROR] No valid fallback raw JSON found.")
            return fail_job(
                summary,
                summary_path,
                "no reviews extracted and no valid fallback raw JSON found",
                {
                    "name": "crawl",
                    "status": "FAILED",
                    "output": relative_path(raw_path),
                    "review_count": 0,
                },
            )

        review_count = current_fallback_review_count
        summary["used_fallback_raw_json"] = True
        print(f"[INFO] Fallback reviews loaded: {review_count}")
        summary["steps"].append(
            {
                "name": "crawl",
                "status": "FALLBACK_USED",
                "output": relative_path(raw_path),
                "review_count": review_count,
                "message": (
                    "crawler returned no reviews; existing raw JSON "
                    "fallback used"
                ),
            }
        )
    else:
        print(f"[INFO] Reviews crawled: {review_count}")
        summary["steps"].append(
            {
                "name": "crawl",
                "status": "DONE",
                "output": relative_path(raw_path),
                "review_count": review_count,
            }
        )

    if crawler_start_error is not None:
        print(f"[WARN] Crawler process could not start: {crawler_start_error}")
    elif crawler_result is not None and crawler_result.returncode != 0:
        print(
            "[WARN] Crawler subprocess returned code "
            f"{crawler_result.returncode}."
        )

    analyzer_script = (
        PROJECT_ROOT / "scripts" / "analyze_crawled_naver_reviews.py"
    )
    rti_signature_before = file_signature(rti_path)
    if used_fallback:
        print("[INFO] Running RTI analyzer with fallback raw JSON...")
    else:
        print("[INFO] Running RTI analyzer...")
    try:
        analyzer_result = run_script(
            analyzer_script,
            relative_path(raw_path),
        )
    except OSError as error:
        return fail_job(
            summary,
            summary_path,
            f"failed to start RTI analyzer: {error}",
            {"name": "rti_analysis", "status": "FAILED"},
        )

    if analyzer_result.returncode != 0:
        return fail_job(
            summary,
            summary_path,
            f"RTI analyzer subprocess failed with return code "
            f"{analyzer_result.returncode}",
            {
                "name": "rti_analysis",
                "status": "FAILED",
                "output": relative_path(rti_path),
            },
        )

    if not rti_path.is_file():
        return fail_job(
            summary,
            summary_path,
            "RTI result JSON file not found",
            {
                "name": "rti_analysis",
                "status": "FAILED",
                "output": relative_path(rti_path),
            },
        )

    if file_signature(rti_path) == rti_signature_before:
        return fail_job(
            summary,
            summary_path,
            "RTI result JSON was not generated by the analyzer run",
            {
                "name": "rti_analysis",
                "status": "FAILED",
                "output": relative_path(rti_path),
            },
        )

    try:
        rti_data = load_json_object(rti_path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return fail_job(
            summary,
            summary_path,
            f"invalid RTI result JSON: {error}",
            {
                "name": "rti_analysis",
                "status": "FAILED",
                "output": relative_path(rti_path),
            },
        )

    analyzed_count = rti_data.get("analyzed_count")
    if (
        isinstance(analyzed_count, bool)
        or not isinstance(analyzed_count, int)
        or analyzed_count < 1
    ):
        return fail_job(
            summary,
            summary_path,
            "no reviews analyzed",
            {
                "name": "rti_analysis",
                "status": "FAILED",
                "output": relative_path(rti_path),
                "analyzed_count": analyzed_count,
            },
        )

    print(f"[INFO] Reviews analyzed: {analyzed_count}")
    summary["steps"].append(
        {
            "name": "rti_analysis",
            "status": "DONE",
            "output": relative_path(rti_path),
            "analyzed_count": analyzed_count,
        }
    )
    summary["status"] = "DONE"
    summary["message"] = "local worker simulation completed"
    save_summary(summary, summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
