"""Deprecated: 이전 Redis 실행 명령에 이관 안내를 제공한다."""


if __name__ == "__main__":
    raise SystemExit("Redis worker retired. Use: uvicorn main:app --host 0.0.0.0 --port 8000")
