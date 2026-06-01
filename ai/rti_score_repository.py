import json


def parse_reasons(raw_reasons) -> list:
    if not raw_reasons:
        return []

    try:
        parsed = json.loads(raw_reasons)
    except (TypeError, json.JSONDecodeError):
        return []

    if isinstance(parsed, list):
        return parsed

    return []


def get_saved_rti_score(cursor, review_id: str) -> dict | None:
    cursor.execute(
        """
        SELECT
            review_id,
            rti,
            level,
            text_score,
            behavior_score,
            network_score,
            reasons
        FROM review_trust_scores
        WHERE review_id = ?
        ORDER BY score_id DESC
        LIMIT 1
        """,
        (review_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "review_id": str(row["review_id"]),
        "rti": row["rti"],
        "level": row["level"],
        "signals": {
            "text": row["text_score"],
            "behavior": row["behavior_score"],
            "network": row["network_score"],
        },
        "reasons": parse_reasons(row["reasons"]),
    }
