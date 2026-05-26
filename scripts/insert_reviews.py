import json
import sqlite3
from pathlib import Path


DB_PATH = Path("review_system.db")
INPUT_PATH = Path("data/input_reviews_sample.json")


def connect_db():
    return sqlite3.connect(DB_PATH)


def load_input_data(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def upsert_product(cursor, product: dict):
    cursor.execute(
        """
        INSERT INTO products (
            product_id,
            name,
            product_url,
            category
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            name = excluded.name,
            product_url = excluded.product_url,
            category = excluded.category
        """,
        (
            product.get("product_id"),
            product.get("product_name"),
            product.get("product_url"),
            product.get("category"),
        ),
    )


def review_exists(cursor, review_id: str) -> bool:
    cursor.execute(
        "SELECT review_id FROM reviews WHERE review_id = ?",
        (review_id,),
    )
    return cursor.fetchone() is not None


def insert_review(cursor, product_id: str, review: dict):
    cursor.execute(
        """
        INSERT INTO reviews (
            review_id,
            product_id,
            user_id,
            rating,
            content,
            review_date,
            verified_purchase,
            account_age_days,
            reviews_written_today,
            similar_review_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review.get("review_id"),
            product_id,
            review.get("user_id"),
            int(review.get("rating", 0)),
            review.get("content", ""),
            review.get("review_date"),
            bool(review.get("verified_purchase", False)),
            review.get("account_age_days"),
            int(review.get("reviews_written_today", 1)),
            int(review.get("similar_review_count", 0)),
        ),
    )


def insert_reviews_batch(data: dict):
    product = data.get("product", {})
    reviews = data.get("reviews", [])

    product_id = product.get("product_id")

    if not product_id:
        raise ValueError("product.product_id is required")

    conn = connect_db()
    cursor = conn.cursor()

    inserted_count = 0
    skipped_count = 0

    upsert_product(cursor, product)

    for review in reviews:
        review_id = str(review.get("review_id"))

        if not review_id or review_id == "None":
            skipped_count += 1
            continue

        if review_exists(cursor, review_id):
            skipped_count += 1
            continue

        insert_review(cursor, product_id, review)
        inserted_count += 1

    conn.commit()
    conn.close()

    return inserted_count, skipped_count


def main():
    data = load_input_data(INPUT_PATH)
    inserted_count, skipped_count = insert_reviews_batch(data)

    print("Review insert completed.")
    print(f"Inserted reviews: {inserted_count}")
    print(f"Skipped reviews: {skipped_count}")


if __name__ == "__main__":
    main()