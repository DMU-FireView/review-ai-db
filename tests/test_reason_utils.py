"""RTI 사유 태그와 대표 신호 추출 로직을 간단히 검증한다."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from ai.reason_utils import create_tags_from_reasons, extract_key_signal_from_results


def main():
    sample_results = [
        {
            "review_id": "r001",
            "reasons": [
                {"code": "REPETITIVE_KEYWORD", "message": "반복 표현 탐지"},
                {"code": "PURCHASE_UNKNOWN", "message": "구매 여부 확인 불가"},
            ],
        },
        {
            "review_id": "r002",
            "reasons": [
                {"code": "REPETITIVE_KEYWORD", "message": "반복 표현 탐지"},
            ],
        },
    ]

    tags = create_tags_from_reasons(sample_results[0]["reasons"])
    key_signal = extract_key_signal_from_results(sample_results)

    print("tags:", tags)
    print("key_signal:", key_signal)


if __name__ == "__main__":
    main()
