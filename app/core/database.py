"""Deprecated: AI 서버의 직접 DB 접근은 종료되었다. 스키마 참고 자료는 db/에 보존한다."""


def get_db_connection():
    raise RuntimeError("DB access retired: Data server owns review storage. Use POST /api/v1/analyze.")


def db_connection():
    return get_db_connection()


def init_db():
    return get_db_connection()
