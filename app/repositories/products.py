"""MySQL에서 상품 식별자와 상품명을 조회하는 저장소이다."""

from app.api.schemas import TriggerRequest
from app.core.database import db_connection


def resolve_product_id(payload: TriggerRequest) -> str:
    target_id = payload.product_id
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT product_id FROM products WHERE product_id = %s",
                (target_id,),
            )
            row = cursor.fetchone()
            target_url = payload.url or payload.page_url or payload.product_url
            if not row and target_url:
                cursor.execute(
                    "SELECT product_id FROM products WHERE product_url = %s",
                    (target_url,),
                )
                row = cursor.fetchone()
                if row:
                    target_id = row["product_id"]
    return target_id


def get_product_name(product_id: str) -> str | None:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM products WHERE product_id = %s",
                (product_id,),
            )
            row = cursor.fetchone()
    return row["name"] if row else None
