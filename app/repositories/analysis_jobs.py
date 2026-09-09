"""분석 작업·원본 입력·최종 결과를 전용 SQLite 파일에 원자적으로 보관한다."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class JobStore(Protocol):
    def initialize(self) -> None: ...
    def create(self, payload: dict) -> str: ...
    def save_input(self, job_id: str, payload: dict) -> None: ...
    def complete(self, job_id: str, result: dict) -> None: ...
    def fail(self, job_id: str, code: str) -> None: ...
    def get(self, job_id: str) -> dict | None: ...


class SQLiteJobStore:
    def __init__(self, path: str):
        self.path = path

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS ai_analysis_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT,
                error_code TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")

    def create(self, payload: dict) -> str:
        job_id = str(uuid4())
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO ai_analysis_jobs(job_id,status,request_json) VALUES (?, 'RUNNING', ?)",
                (job_id, json.dumps(payload, ensure_ascii=False)),
            )
        return job_id

    def save_input(self, job_id: str, payload: dict) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE ai_analysis_jobs SET request_json=?, updated_at=CURRENT_TIMESTAMP WHERE job_id=?",
                (json.dumps(payload, ensure_ascii=False), job_id),
            )

    def complete(self, job_id: str, result: dict) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """UPDATE ai_analysis_jobs SET status='DONE', result_json=?,
                error_code=NULL, updated_at=CURRENT_TIMESTAMP WHERE job_id=?""",
                (json.dumps(result, ensure_ascii=False), job_id),
            )

    def fail(self, job_id: str, code: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """UPDATE ai_analysis_jobs SET status='FAILED', error_code=?,
                updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status='RUNNING'""",
                (code, job_id),
            )

    def get(self, job_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM ai_analysis_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        raw = result.pop("result_json")
        result["result"] = json.loads(raw) if raw else None
        return result
