"""Deprecated: Redis 큐 처리는 Data 서버의 책임이며 AI 서버는 HTTP만 제공한다."""


def start_worker():
    raise RuntimeError("Redis worker retired. Start uvicorn main:app and use POST /api/v1/analyze.")


def get_redis_client():
    return start_worker()


if __name__ == "__main__":
    start_worker()
