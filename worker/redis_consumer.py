"""Compatibility entry point for the existing worker command."""

from app.worker.consumer import get_redis_client, start_worker


if __name__ == "__main__":
    start_worker()
