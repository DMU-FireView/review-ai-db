import json
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from ai.rti_score_repository import get_saved_rti_score


DB_PATH = PROJECT_ROOT / "review_system.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT review_id
        FROM review_trust_scores
        ORDER BY score_id DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        print("No saved RTI scores found.")
        print("Run scripts/save_rti_scores.py first.")
        return

    result = get_saved_rti_score(cursor, str(row["review_id"]))
    conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
