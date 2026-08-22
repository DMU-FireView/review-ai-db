"""MySQL 연결 수명주기와 서비스 구동 시 필요한 테이블 초기화를 담당한다."""

from collections.abc import Iterator
from contextlib import contextmanager

import pymysql
from pymysql.connections import Connection

from app.core.config import settings


def get_db_connection() -> Connection:
    return pymysql.connect(
        host=settings.db_host,
        user=settings.db_user,
        port=settings.db_port,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


@contextmanager
def db_connection() -> Iterator[Connection]:
    connection = get_db_connection()
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    product_url TEXT,
                    category VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id BIGINT PRIMARY KEY,
                    product_id VARCHAR(50) NOT NULL,
                    user_id VARCHAR(100) NOT NULL,
                    rating INT NOT NULL,
                    content TEXT NOT NULL,
                    review_date DATE NOT NULL,
                    verified_purchase BOOLEAN DEFAULT FALSE,
                    account_age_days INT,
                    reviews_written_today INT,
                    similar_review_count INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS review_trust_scores (
                    score_id INT AUTO_INCREMENT PRIMARY KEY,
                    review_id BIGINT NOT NULL,
                    rti INT NOT NULL,
                    level VARCHAR(20) NOT NULL,
                    text_score INT NOT NULL,
                    behavior_score INT NOT NULL,
                    network_score INT NOT NULL,
                    reasons TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (review_id) REFERENCES reviews(review_id)
                )
                """
            )
        connection.commit()
