from collections import Counter
from typing import Any


def create_tags_from_reasons(reasons: list[dict[str, Any]]) -> list[str]:
    """
    ReasonObject 배열에서 화면용 tag 문자열 배열을 생성합니다.

    입력 예:
    [
        {"code": "REPETITIVE_KEYWORD", "message": "반복 표현 탐지"},
        {"code": "PURCHASE_UNKNOWN", "message": "구매 여부 확인 불가"}
    ]

    출력 예:
    ["반복 표현 탐지", "구매 여부 확인 불가"]
    """

    tags = []

    for reason in reasons:
        message = reason.get("message")

        if message and message not in tags:
            tags.append(message)

    return tags


def extract_key_signal_from_results(results: list[dict[str, Any]]) -> str | None:
    """
    상품 단위 분석 결과에서 가장 많이 등장한 reason code를 대표 신호로 선정합니다.

    입력 예:
    [
        {
            "review_id": "r001",
            "reasons": [
                {"code": "REPETITIVE_KEYWORD", "message": "반복 표현 탐지"}
            ]
        }
    ]

    출력 예:
    "반복 표현 탐지"
    """

    code_counter = Counter()
    code_to_message = {}

    for result in results:
        for reason in result.get("reasons", []):
            code = reason.get("code")
            message = reason.get("message")

            if not code:
                continue

            code_counter[code] += 1

            if message:
                code_to_message[code] = message

    if not code_counter:
        return None

    top_code = code_counter.most_common(1)[0][0]

    return code_to_message.get(top_code, top_code)