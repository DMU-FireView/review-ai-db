"""MySQL 리뷰 행을 분석용 ReviewInput 목록으로 조회·변환한다."""

from app.api.schemas import ReviewInput
from app.core.database import db_connection


def find_by_product_id(product_id: str) -> list[ReviewInput]:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM reviews WHERE product_id = %s",
                (product_id,),
            )
            rows = cursor.fetchall()

    return [
        ReviewInput(
            review_id=str(row["review_id"]),
            product_id=row["product_id"],
            content=row["content"],
            rating=row["rating"],
            user_id=row["user_id"],
            review_date=str(row["review_date"]),
            verified_purchase=bool(row["verified_purchase"]),
            reviews_written_today=row["reviews_written_today"] or 1,
            similar_review_count=row["similar_review_count"] or 0,
            image_count=0,
            quality_score=0.5,
            repurchase="unknown",
            free_trial="unknown",
        )
        for row in rows
    ]
