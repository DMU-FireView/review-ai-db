"""변환된 리뷰 JSON을 로컬 SQLite 리뷰 테이블에 적재한다."""

import json
from pathlib import Path

from insert_reviews import insert_reviews_batch


INPUT_DIR = Path("data/converted/products")


def load_json_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    json_paths = sorted(INPUT_DIR.glob("*.json"))

    if not json_paths:
        print("No converted product JSON files found.")
        print(f"Input dir: {INPUT_DIR}")
        print("Run the converter first or place product JSON files in the input dir.")
        return

    product_count = 0
    inserted_total = 0
    skipped_total = 0

    for path in json_paths:
        data = load_json_file(path)
        inserted_count, skipped_count = insert_reviews_batch(data)

        product_count += 1
        inserted_total += inserted_count
        skipped_total += skipped_count

        print(
            f"{path.name}: inserted={inserted_count}, "
            f"skipped={skipped_count}"
        )

    print("Converted review insert completed.")
    print(f"product_count: {product_count}")
    print(f"inserted_total: {inserted_total}")
    print(f"skipped_total: {skipped_total}")


if __name__ == "__main__":
    main()
