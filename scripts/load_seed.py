"""DB 시드 SQL을 로컬 SQLite 데이터베이스에 적용한다."""

import sqlite3
from pathlib import Path


DB_PATH = Path("review_system.db")
INIT_SQL_PATH = Path("db/init.sql")
SEED_SQL_PATH = Path("db/seed.sql")


def execute_sql_file(cursor, path: Path):
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")

    sql = path.read_text(encoding="utf-8")
    cursor.executescript(sql)


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    execute_sql_file(cursor, INIT_SQL_PATH)
    execute_sql_file(cursor, SEED_SQL_PATH)

    conn.commit()
    conn.close()

    print("DB init and seed completed.")
    print(f"DB path: {DB_PATH}")


if __name__ == "__main__":
    main()
