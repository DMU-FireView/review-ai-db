# Re:view AI 분석·저장 서비스 (수집/SSE 통합 준비)

Data 서버가 HTTP로 전달한 리뷰를 분석해 JSON을 반환합니다.
분석 결과는 AI 자체 SQLite DB에 먼저 저장합니다. Redis는 사용하지 않습니다.
팀원 저장소의 크롤러 SSE 수신 계약을 통합했으며 새 공개 계약은 아직 미확정입니다.
수집/SSE 실험 경로는 기본 비활성화입니다. [통합 상태·미확정 사항](docs/integration-preparation.md)을 먼저 확인하세요.

## 현재 상태와 역할

| 구분 | 현재 범위 |
| --- | --- |
| 기본 기능 | 리뷰 배치 분석, AI 자체 DB에 입력·결과 저장, 저장 성공 후 JSON 응답 |
| 실험 기능 (기본 OFF) | 외부 크롤러 SSE 수신, 수집 진행 알림, 분석 중 heartbeat, 저장 결과 조회 |
| 미구현 | 프로세스 재시작 후 작업 자동 재개, 멱등 요청, 결과 자동 재전송 |
| 팀 합의 필요 | 최종 API·인증, 크롤러 누락 신호 처리, 최종 분석기, 운영 DB·백업·보존 정책 |

기본 API 처리 순서는 **요청 → 입력 저장 → 점수 계산 → 결과 저장 → HTTP 응답**입니다.
현재는 `202`로 접수만 알리는 작업 큐가 아니라, 계산·저장을 마친 최종 결과를 반환합니다.
크롤링 자체는 외부 크롤러가 담당하며, 이 저장소의 실험 기능은 그 스트림을 받아 분석에 연결합니다.
팀원 `review-ai-new`의 수신 계약은 가져왔지만, 다른 점수 알고리즘을 덮어쓰지는 않았습니다.

> 현재 API에는 인증이 없습니다. 로컬 검증을 먼저 진행하고, 운영 공개 전에 접근 제어와
> 팀 연동 계약을 확정하세요. DB 저장은 클라이언트의 결과 수신까지 보장하지 않습니다.

## 빠른 시작

Python 3.12와 Git이 필요합니다. 이미 저장소가 있다면 복제 단계는 건너뛰고
프로젝트 루트에서 실행하세요. 기존 `.env`와 `.venv`는 덮어쓰지 않습니다.

### 1. 설치와 서버 실행 (Windows PowerShell)

```powershell
git clone --branch codex/modular-project-cleanup https://github.com/DMU-FireView/review-ai-db.git
cd review-ai-db
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 첫 실행은 실험 기능과 외부 감성 API를 끈 로컬 평가로 확인합니다.
$env:PYTHON_DOTENV_DISABLED = "1"
$env:ENABLE_EXPERIMENTAL_COLLECTION = "0"
$env:ALLOW_LEGACY_CRAWLER_DEFAULTS = "0"
$env:GOOGLE_APPLICATION_CREDENTIALS = ""
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

macOS/Linux에서는 가상환경 생성·설치·실행 명령을 다음처럼 바꾸면 됩니다.
`.env`가 없다면 `.env.example`을 복사하고, 기존 설정이 있다면 먼저 확인하세요.

```sh
if [ ! -d .venv ]; then python3.12 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHON_DOTENV_DISABLED=1 ENABLE_EXPERIMENTAL_COLLECTION=0 ALLOW_LEGACY_CRAWLER_DEFAULTS=0 GOOGLE_APPLICATION_CREDENTIALS="" \
  .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

서버가 켜지면 [Swagger UI](http://localhost:8000/docs)에서 API를 실행할 수 있습니다.
종료는 서버 터미널에서 Ctrl+C를 누릅니다.
위 예시는 기존 `.env`의 영향을 피하려고 자동 로딩을 끕니다. `.env` 설정을 사용하려면
새 터미널에서 `PYTHON_DOTENV_DISABLED`를 설정하지 않고 실행하세요.

### 2. 첫 분석 요청

서버는 켜둔 채 **새 PowerShell 터미널**에서 실행합니다.

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"

$analysisBody = @{
    product_id = "A001"
    reviews = @(
        @{
            review_id = "1001"
            content = "배송 빠르고 제품도 좋아요"
            user_id = "user1"
            review_date = "2026-09-08"
            verified_purchase = $true
        }
    )
} | ConvertTo-Json -Depth 5

$analysisResponse = Invoke-WebRequest -Method Post `
    -Uri "http://localhost:8000/api/v1/analyze" `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($analysisBody))

$analysisResponse.StatusCode
$analysisResponse.Headers["X-Analysis-Job-ID"]
$analysisResponse.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

기대 결과는 health의 `status: ok`, 분석 HTTP `200`, RTI `88`, 등급 `safe`입니다.
이 점수는 위 예제와 Google 감성 API 비활성화 조건 기준입니다.
macOS/Linux에서는 Swagger UI의 `POST /api/v1/analyze` → **Try it out**에
아래 API 절의 JSON을 넣어 동일하게 확인할 수 있습니다.

로컬 DB 기본 경로는 `data/ai-results.db`이며 시작 시 생성합니다.
`AI_RESULT_DB_PATH`를 설정하면 경로를 바꿀 수 있고 해당 위치에 쓰기 권한이 필요합니다.
정상 분석 응답은 결과의 DB 커밋이 완료된 뒤 반환됩니다.
작업 ID 헤더는 저장 기록 식별용이며, 기본 API에는 공개 결과 조회 경로가 없습니다.

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
기존 분석 API는 입력 순서를 유지하며 리뷰를 자동 수집·중복 제거하지 않습니다.
작업·입력·분석 결과를 DB에 저장하고, 성공 응답에 X-Analysis-Job-ID 헤더를 추가합니다.
계산 또는 저장 실패 시 성공 결과 대신 503을 반환합니다.

RTI = Python round(text × 0.4 + behavior × 0.35 + network × 0.25).
50 미만 danger, 50 이상 80 미만 warn, 80 이상 safe입니다.
기존 사유 순서(text → behavior → network)와 input_features 문자열 변환도 유지합니다.

## 테스트와 Docker 실행

프로젝트 루트에서 테스트를 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

macOS/Linux에서는 `.venv/bin/python -m pytest -q`를 사용합니다.
2026-09-09 검증 기록은 42개 통과입니다. 가짜 크롤러 SSE와 로컬 DB를 사용하는 테스트이며,
실제 크롤러·Spring·Azure 연동 검증을 대신하지 않습니다.

Docker Desktop의 **Linux 엔진** 또는 Linux Docker Engine이 실행 중이어야 합니다.
로컬 Uvicorn이 8000 포트를 쓰고 있다면 먼저 종료하세요.

```sh
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 50 ai
```

이후 위의 health·분석 요청으로 확인합니다. 2026-09-09 통합 변경 당시에는
엔진 미실행으로 새 이미지 빌드·실행 검증을 완료하지 못했습니다.

Docker에는 AI 서비스 한 개만 있으며 비-root 사용자로 실행합니다.
소스·실행 의존성만 복사하고 .env, 데이터, 팀원 DB, artifacts, 크롤링 도구는 제외합니다.
production에서는 reload를 사용하지 않습니다.
결과 DB는 컨테이너의 `/service/data/ai-results.db`에 생성하고 `ai-results` named volume에 보관합니다.
일반 `docker compose down`은 볼륨을 유지하지만 **`docker compose down -v`는 결과 볼륨을
삭제하므로 사용하지 마세요.** 볼륨 보존과 별도로 운영 백업이 필요합니다.

## 실험적 수집/SSE

최종 공개 계약이 아닌 개발용 기능입니다. 기본 실행에서는 다음 경로가 등록되지 않아 404입니다.

- `POST /experimental/analysis/collect/stream`
- `GET /experimental/analysis/jobs/{job_id}`

실험 경로 등록에는 `ENABLE_EXPERIMENTAL_COLLECTION=1`과 명시적 `CRAWLER_BASE_URL`이 필요합니다.
크롤러 입력에는 기존 분석기에 필요한 일부 신호가 없으므로,
수집 분석은 `ALLOW_LEGACY_CRAWLER_DEFAULTS=1`까지 승인하지 않으면 503으로 차단합니다.
팀 합의 없이 이 설정을 운영에서 켜지 마세요.
세부 입력 매핑·이벤트·연결 중단 한계는 [통합 준비 문서](docs/integration-preparation.md)에 정리돼 있습니다.

## 구조와 기존 파일

- main.py: 기존 ASGI 진입점과 분석 import 호환
- app/api/: HTTP 요청·응답 DTO와 라우팅
- app/factory.py: 전용 결과 저장소 초기화와 선택적 크롤러 client 수명 관리
- app/repositories/analysis_jobs.py: 독립 SQLite 작업/결과 저장소
- app/contracts/, app/integrations/: 크롤러 SSE 계약과 수신 어댑터
- app/services/collection_stream.py: 수집 진행, 분석 중 heartbeat, 저장 후 result
- ai/analysis.py: 기존 RTI 통합 공식
- ai/text_analyzer.py, behavior_analyzer.py, network_analyzer.py: 변경 없는 분석 알고리즘
- ai/sentiment_client.py: 기존 선택적 Google Cloud 감성 분석
- tests/: HTTP·입력 검증·점수 회귀 검사
- scripts/, db/, 기존 repository/crawler/product 서비스: 과거 개발 참고용 보존 (새 결과 DB와 별개)
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
