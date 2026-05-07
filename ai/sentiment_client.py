import os


def is_cloud_nlp_enabled():
    """
    Google Cloud Natural Language API 사용 여부를 확인합니다.

    기본값은 False입니다.
    실제 API 연결 전까지는 로컬 mock/fallback 모드로 동작합니다.
    """
    return os.getenv("ENABLE_CLOUD_NLP", "false").lower() == "true"


def analyze_sentiment(text):
    """
    리뷰 본문 감성 분석 함수

    현재 v0에서는 실제 Google Cloud Natural Language API를 호출하지 않고,
    neutral mock 결과를 반환합니다.

    추후 ENABLE_CLOUD_NLP=true 설정 후 실제 API 호출 로직을 연결할 예정입니다.
    """

    text = text or ""

    if not is_cloud_nlp_enabled():
        return {
            "enabled": False,
            "source": "mock",
            "score": 0.0,
            "magnitude": 0.0,
            "reason": "Cloud Natural Language API disabled"
        }

    # 실제 Google Cloud Natural Language API 연결은 다음 단계에서 구현 예정
    # 현재는 API 키/인증 정보가 없어도 로컬 실행이 깨지지 않도록 fallback 처리
    try:
        from google.cloud import language_v1 as language

        client = language.LanguageServiceClient()

        document = language.Document(
            content=text,
            type_=language.Document.Type.PLAIN_TEXT,
            language="ko"
        )

        response = client.analyze_sentiment(
            request={
                "document": document,
                "encoding_type": language.EncodingType.UTF8
            }
        )

        sentiment = response.document_sentiment

        return {
            "enabled": True,
            "source": "google_cloud_natural_language",
            "score": sentiment.score,
            "magnitude": sentiment.magnitude,
            "reason": "Cloud Natural Language API sentiment analyzed"
        }

    except Exception as error:
        return {
            "enabled": False,
            "source": "fallback",
            "score": 0.0,
            "magnitude": 0.0,
            "reason": f"Cloud Natural Language API fallback: {error}"
        }
