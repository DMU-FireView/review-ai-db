# Re:view AI 독립 분석 서비스

Data 서버가 HTTP로 전달한 리뷰를 분석해 JSON을 반환합니다.
크롤링·작업 오케스트레이션·PostgreSQL 저장은 Data 서버의 책임입니다.
AI 서버는 DB와 Redis 없이 시작합니다.

## API

- `GET /health`: `{"status":"ok"}`
- `POST /api/v1/analyze`: 리뷰 배치 분석
- `GET /docs`, `GET /redoc`, `GET /openapi.json`: API 문서
- `GET /`: /docs로 이동

```json
{
  "product_id": "A001",
  "reviews": [{
    "review_id": "1001",
    "content": "배송 빠르고 제품도 좋아요",
    "rating": 5,
    "user_id": "user1",
    "review_date": "2026-09-08",
    "verified_purchase": true,
    "account_age_days": 500,
    "reviews_written_today": 1,
    "similar_review_count": 0
  }]
}
```

Google 인증 미설정 시 위 입력의 실제 응답:

```json
{
  "product_id": "A001",
  "results": [{
    "review_id": "1001",
    "content": "배송 빠르고 제품도 좋아요",
    "author": "user1",
    "date": "2026-09-08",
    "rti": 88,
    "level": "safe",
    "signals": {"text": 75, "behavior": 95, "network": 100},
    "input_features": {
      "image_count": 0, "quality_score": null,
      "verified_purchase": "True", "repurchase": "unknown", "free_trial": "unknown",
      "reviews_written_today": 1, "similar_review_count": 0
    },
    "reasons": [
      {"code": "SHORT_REVIEW", "message": "리뷰 내용이 지나치게 짧음"},
      {"code": "NO_IMAGE_ATTACHED", "message": "이미지 첨부 없음"}
    ]
  }]
}
```

필수 필드: product_id, reviews(1개 이상), 각 리뷰의 review_id/content/user_id/review_date.
누락·빈 배열·잘못된 타입·범위·알 수 없는 입력 필드는 422입니다.
rating은 기본 5(1~5), 개수 필드는 음수가 아닌 정수입니다.
verified_purchase/repurchase/free_trial은 boolean 또는 "unknown"입니다.
review_date는 기존 문자열 계약을 유지합니다.
account_age_days는 허용하지만 현재 점수에 사용하지 않습니다.
입력 순서를 유지하며 리뷰를 자동 수집·중복 제거하거나 DB에 저장하지 않습니다.

RTI = Python round(text × 0.4 + behavior × 0.35 + network × 0.25).
50 미만 danger, 50 이상 80 미만 warn, 80 이상 safe입니다.
기존 사유 순서(text → behavior → network)와 input_features 문자열 변환도 유지합니다.

## 실행

Python 3.12를 기준으로 검증합니다.

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

```sh
docker compose config
docker compose build
docker compose up -d
curl --fail http://localhost:8000/health
```

Docker에는 AI 서비스 한 개만 있으며 비-root 사용자로 실행합니다.
소스·실행 의존성만 복사하고 .env, 데이터, 팀원 DB, artifacts, 크롤링 도구는 제외합니다.
production에서는 reload를 사용하지 않습니다.

## 구조와 기존 파일

- main.py: 기존 ASGI 진입점과 분석 import 호환
- app/api/: HTTP 요청·응답 DTO와 라우팅
- app/factory.py: DB 초기화 없는 앱 생성
- ai/analysis.py: 기존 RTI 통합 공식
- ai/text_analyzer.py, behavior_analyzer.py, network_analyzer.py: 변경 없는 분석 알고리즘
- ai/sentiment_client.py: 기존 선택적 Google Cloud 감성 분석
- tests/: HTTP·입력 검증·점수 회귀 검사
- scripts/, db/, 기존 repository/crawler/product 서비스: 과거 개발 참고용 보존
- app/core/database.py, app/worker/consumer.py, worker/redis_consumer.py: deprecated 안내만 제공

과거 DB 조회 API 5개(/api/internal/ai/...)는 등록을 해제했으며 404입니다.
Data 서버는 상품 ID만 보내던 방식에서 실제 reviews를 보내는 방식으로 전환해야 합니다.
크롤링 참고 도구가 필요하면 requirements-legacy.txt를 별도로 설치합니다.
SQLite 검증 스크립트는 production API 테스트와 별개입니다.

## Google Cloud 선택 기능

GOOGLE_APPLICATION_CREDENTIALS가 설정되면 기존 감성 API를 사용합니다.
미설정 또는 호출 실패 시 기존 fallback을 유지합니다.
ENABLE_CLOUD_NLP는 기존 코드에서도 읽지 않았으므로 새 설정으로 사용하지 않습니다.
인증 JSON을 코드나 이미지에 넣지 마세요.

호스트의 인증 파일을 별도로 준비하고 컨테이너 uid 10001이 읽을 수 있도록 한 후:

```sh
export GOOGLE_CREDENTIALS_FILE=/absolute/secure/google-credentials.json
sudo --preserve-env=GOOGLE_CREDENTIALS_FILE docker compose -f docker-compose.yml -f compose.google.yml up -d --build
```

자동 배포에도 사용하려면 VM의 docker-compose.override.yml에 같은 읽기 전용
마운트와 GOOGLE_APPLICATION_CREDENTIALS 설정을 추가합니다.
실제 인증 파일은 VM에 보관하며 GitHub workflow는 .env를 생성하거나 덮어쓰지 않습니다.

새 VM 설치와 배포 절차: [Azure 배포 안내](docs/azure-ai-deployment.md).
전환 분석과 보존/종료 범위: [독립 서비스 전환 기록](docs/ai-service-migration.md).
