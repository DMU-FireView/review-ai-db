"""Redis 분석 작업 큐를 구독하는 비동기 Worker 골격을 제공한다."""

import json
import time

import redis

from app.core.config import settings


QUEUE_NAME = "review_analysis_queue"


def get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=0,
        decode_responses=True,
    )


def start_worker() -> None:
    client = get_redis_client()
    print(
        "FastAPI Worker 시작: "
        f"Redis({settings.redis_host}:{settings.redis_port}) 큐 대기 중"
    )
    while True:
        try:
            _, message = client.blpop(QUEUE_NAME)
            job = json.loads(message)
            print(
                "Job 수신: "
                f"id={job.get('jobId')}, "
                f"platform={job.get('platform', 'NAVER')}, "
                f"url={job.get('productUrl')}"
            )
            # 실제 처리는 app.services.job에 연결한다.
        except Exception as error:
            print(f"Job 처리 중 오류 발생: {error}")
            time.sleep(2)


if __name__ == "__main__":
    start_worker()
