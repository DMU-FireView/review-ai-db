import json
import sqlite3
from pathlib import Path

from main import ReviewInput, analyze_single_review


DB_PATH = Path("review_system.db")


def fetch_reviews(cursor):
    cursor.execute(
        """
        SELECT
            review_id,
            product_id,
            user_id,
            rating,
            content,
            review_date,
            verified_purchase,
            reviews_written_today,
            similar_review_count
        FROM reviews
        """
    )
    return cursor.fetchall()


def score_exists(cursor, review_id: str) -> bool:
    cursor.execute(
        "SELECT score_id FROM review_trust_scores WHERE review_id = ?",
        (review_id,),
    )
    return cursor.fetchone() is not None


def save_score(cursor, review, result):
    reasons_json = json.dumps(
        [reason.model_dump() for reason in result.reasons],
        ensure_ascii=False,
    )

    cursor.execute(
        """
        INSERT INTO review_trust_scores (
            review_id,
            rti,
            level,
            text_score,
            behavior_score,
            network_score,
            reasons
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review["review_id"],
            result.rti,
            result.level,
            result.signals.text,
            result.signals.behavior,
            result.signals.network,
            reasons_json,
        ),
    )


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    reviews = fetch_reviews(cursor)

    inserted_count = 0
    skipped_count = 0

    for row in reviews:
        review_id = str(row["review_id"])

        if score_exists(cursor, review_id):
            skipped_count += 1
            continue

        review_input = ReviewInput(
            review_id=review_id,
            product_id=str(row["product_id"]),
            user_id=str(row["user_id"]),
            content=row["content"],
            review_date=str(row["review_date"]),
            rating=int(row["rating"]),
            verified_purchase=bool(row["verified_purchase"]),
            reviews_written_today=int(row["reviews_written_today"] or 1),
            similar_review_count=int(row["similar_review_count"] or 0),
            image_count=0,
            quality_score=0.5,
            repurchase="unknown",
            free_trial="unknown",
        )

        result = analyze_single_review(review_input)
        save_score(cursor, row, result)
        inserted_count += 1

    conn.commit()
    conn.close()

    print("RTI score save completed.")
    print(f"Inserted scores: {inserted_count}")
    print(f"Skipped scores: {skipped_count}")


if __name__ == "__main__":
    main()