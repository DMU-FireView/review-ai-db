"""Deprecated: AI 서버의 직접 DB 접근은 종료되었다. 스키마 참고 자료는 db/에 보존한다."""


def get_db_connection():
    raise RuntimeError("Legacy DB access retired. Use POST /api/v1/data/analyze; AI job storage is managed by MySQLJobStore.")


def db_connection():
    return get_db_connection()


def init_db():
    return get_db_connection()
