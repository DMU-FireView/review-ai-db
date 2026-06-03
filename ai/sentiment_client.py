import os
from typing import Dict


def analyze_sentiment(content: str) -> Dict[str, float | bool]:
    """
    GCP Natural Language API를 사용해 리뷰 감성 분석을 수행합니다.

    반환 구조:
    - enabled: GCP 감성 분석 사용 여부
    - score: 감성 점수 (-1.0 ~ 1.0)
    - magnitude: 감성 강도
    """

    if not content:
        return {
            "enabled": False,
            "score": 0.0,
            "magnitude": 0.0,
        }

    # GCP 인증 키가 없으면 감성 분석 비활성화
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return {
            "enabled": False,
            "score": 0.0,
            "magnitude": 0.0,
        }

    try:
        from google.cloud import language_v1

        client = language_v1.LanguageServiceClient()

        document = language_v1.Document(
            content=content,
            type_=language_v1.Document.Type.PLAIN_TEXT,
            language="ko",
        )

        response = client.analyze_sentiment(
            request={
                "document": document,
                "encoding_type": language_v1.EncodingType.UTF8,
            }
        )

        sentiment = response.document_sentiment

        return {
            "enabled": True,
            "score": float(sentiment.score),
            "magnitude": float(sentiment.magnitude),
        }

    except Exception:
        return {
            "enabled": False,
            "score": 0.0,
            "magnitude": 0.0,
        }