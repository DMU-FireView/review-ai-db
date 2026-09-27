# Re:view AI 분석·저장 서비스 (수집/SSE 통합 준비)

Data 서버가 HTTP로 전달한 리뷰를 분석해 JSON을 반환합니다.
분석 결과는 AI 자체 MySQL DB에 먼저 저장합니다. Redis는 사용하지 않습니다.
v0.5 Data 분석 API와 팀원 분석기를 통합했습니다. 공식 분석 경로는 `POST /api/v1/data/analyze`입니다.
새 연동은 [v0.5 API·인증·계산 정책](docs/data-ai-v05-integration.md)을 먼저 확인하세요.
수집/SSE 실험 경로는 기본 비활성화입니다. [통합 상태·미확정 사항](docs/integration-preparation.md)을 먼저 확인하세요.

## 현재 상태와 역할

| 구분 | 현재 범위 |
| --- | --- |
| 기본 기능 | 리뷰 배치 분석, AI 자체 DB에 입력·결과 저장, 저장 성공 후 JSON 응답 |
| 실험 기능 (기본 OFF) | 외부 크롤러 SSE 수신, 수집 진행 알림, 분석 중 heartbeat, 저장 결과 조회 |
| 미구현 | 프로세스 재시작 후 작업 자동 재개, 멱등 요청, 결과 자동 재전송 |
| 팀 합의 필요 | HTTPS·실제 이벤트 샘플, 운영 계정·DB 백업·보존 정책 |

기본 API 처리 순서는 **요청 → 입력 저장 → 점수 계산 → 결과 저장 → HTTP 응답**입니다.
현재는 `202`로 접수만 알리는 작업 큐가 아니라, 계산·저장을 마친 최종 결과를 반환합니다.
크롤링 자체는 외부 크롤러가 담당하며, 이 저장소의 실험 기능은 그 스트림을 받아 분석에 연결합니다.
새 Data API와 SSE는 승인된 팀원 분석기(.5/.3/.2)를 사용합니다.
과거 호환 분석 라우트는 운영 API에서 제거했습니다.

> 운영에서는 `REQUIRE_INTERNAL_TOKEN=1`과 `INTERNAL_TOKEN`을 설정하고 HTTPS로 공개하세요.
> 토큰 미설정·REQUIRE=0은 로컬 호환 모드입니다. DB 저장은 클라이언트의 결과 수신까지 보장하지 않습니다.

## 빠른 시작

Python 3.12와 Git이 필요합니다. 이미 저장소가 있다면 복제 단계는 건너뛰고
프로젝트 루트에서 실행하세요. 기존 `.env`와 `.venv`는 덮어쓰지 않습니다.

### 1. 설치와 서버 실행 (Windows PowerShell)

```powershell
git clone --branch main https://github.com/DMU-FireView/review-ai-db.git
cd review-ai-db
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# .env의 DB_PASSWORD를 기존 MySQL 비밀번호로 설정한 뒤 DB를 실행합니다.
# DB_HOST=127.0.0.1, DB_PORT=3307 (Compose 내부에서는 ai-db:3306)
docker compose up -d ai-db
$env:ENABLE_EXPERIMENTAL_COLLECTION = "0"
$env:GOOGLE_APPLICATION_CREDENTIALS = ""
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

macOS/Linux에서는 가상환경 생성·설치·실행 명령을 다음처럼 바꾸면 됩니다.
`.env`가 없다면 `.env.example`을 복사하고, 기존 설정이 있다면 먼저 확인하세요.

```sh
if [ ! -d .venv ]; then python3.12 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements-dev.txt
docker compose up -d ai-db
ENABLE_EXPERIMENTAL_COLLECTION=0 GOOGLE_APPLICATION_CREDENTIALS="" \
  .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

서버가 켜지면 [Swagger UI](http://localhost:8000/docs)에서 API를 실행할 수 있습니다.
종료는 서버 터미널에서 Ctrl+C를 누릅니다.
위 예시는 `.env`에서 DB 접속 정보를 읽습니다. 기존 터미널에
`PYTHON_DOTENV_DISABLED=1`이 설정되어 있다면 해제하거나 새 터미널에서 실행하세요.

### 2. 공식 Data API 분석 요청

서버는 켜둔 채 **새 PowerShell 터미널**에서 실행합니다. 아래 예시는 로컬 토큰 미설정 기준이며,
인증 사용 시 `-Headers @{"X-Internal-Token"=$env:INTERNAL_TOKEN}`을 추가하세요.

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"

$analysisBody = @{
    platform = "mall"
    product_id = "A001"
    reviews = @(
        @{
            review_id = "1001"
            content = "배송 빠르고 제품도 좋아요"
            written_at = "2026-09-08T00:00:00"
        }
    )
} | ConvertTo-Json -Depth 5

$analysisResponse = Invoke-WebRequest -Method Post `
    -Uri "http://localhost:8000/api/v1/data/analyze" `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($analysisBody))

$analysisResponse.StatusCode
$analysisResponse.Headers["X-Analysis-Job-ID"]
$analysisResponse.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

기대 결과는 health의 `status: ok`, 분석 HTTP `200`, RTI `75`, 등급 `warn`입니다.
이 예시는 비교 리뷰와 행동 근거가 없어 텍스트 점수만 RTI에 반영합니다.
macOS/Linux에서는 Swagger UI의 `POST /api/v1/data/analyze` → **Try it out**에
아래 API 절의 JSON을 넣어 동일하게 확인할 수 있습니다.

기본 저장소는 MySQL의 `review_system.ai_analysis_jobs`입니다.
`DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`으로 접속하며, 시작 시 테이블이 없으면 생성합니다.
접속 실패 시 시작을 중단합니다. SQLite 자동 대체는 없고 `AI_RESULT_DB_PATH`는 사용하지 않습니다.
기존 팀 테이블은 변경하지 않으며, 과거 SQLite 데이터도 삭제하거나 자동 이관하지 않습니다.
정상 분석 응답은 결과의 DB 커밋이 완료된 뒤 반환됩니다.
작업 ID 헤더는 저장 기록 식별용이며, 기본 API에는 공개 결과 조회 경로가 없습니다.

## API

운영 Swagger에는 다음 두 경로만 표시됩니다 (`ENABLE_EXPERIMENTAL_COLLECTION=0`).

- `GET /health`: `{"status":"ok"}`
- `POST /api/v1/data/analyze`: Data/AI v0.5 공식 리뷰 배치 분석

`/docs`, `/redoc`, `/openapi.json`은 API 문서이며 `/`는 문서 화면으로 이동합니다.
토큰을 설정한 경우 분석 요청에 `X-Internal-Token` 헤더가 필요합니다.

요청 예시:

```json
{
  "platform": "mall",
  "product_id": "A001",
  "reviews": [{
    "review_id": "1001",
    "content": "배송 빠르고 제품도 좋아요",
    "rating": 5,
    "written_at": "2026-09-08T00:00:00"
  }]
}
```

응답 예시:

```json
{
  "platform": "mall",
  "product_id": "A001",
  "review_count": 1,
  "results": [{
    "review_id": "1001",
    "rti": 75.0,
    "level": "warn",
    "text_score": 75.0,
    "behavior_score": null,
    "network_score": null,
    "reasons": ["SHORT_REVIEW"]
  }]
}
```

필수 필드는 platform/product_id/reviews와 각 리뷰의 review_id/content입니다.
rating/written_at은 선택입니다. 리뷰 1~500개, 단일 상품 배치이며 ID와 요청 순서를 보존합니다.
누락·중복 리뷰 ID·잘못된 타입·알 수 없는 입력 필드는 422입니다.
기본 가중치는 text/behavior/network = 50/30/20이며 사용 가능한 신호만 재정규화합니다.
근거가 부족한 점수는 null입니다. 80 이상 safe, 50 이상 warn, 50 미만 danger입니다.
작업·입력·결과를 MySQL에 저장하고, 커밋 성공 후 X-Analysis-Job-ID와 최종 결과를 반환합니다.
분석·저장 실패는 503입니다. 자세한 내용은 [v0.5 연동 문서](docs/data-ai-v05-integration.md)를 참고하세요.

`POST /api/v1/analyze`는 **retired legacy endpoint**이며 라우트와 Swagger에서 제거되어 404를 반환합니다.

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
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 50 ai
```

이후 위의 health·분석 요청으로 확인합니다. 2026-09-09 통합 변경 당시에는
엔진 미실행으로 새 이미지 빌드·실행 검증을 완료하지 못했습니다.

Docker에는 AI 서비스와 MySQL 8.0이 있으며 AI 프로세스는 비-root 사용자로 실행합니다.
소스·실행 의존성만 복사하고 .env, 데이터, 팀원 DB, artifacts, 크롤링 도구는 제외합니다.
production에서는 reload를 사용하지 않습니다.
MySQL은 기존 `ai-db-data` 볼륨(`/var/lib/mysql`)을 재사용합니다.
Compose 프로젝트 이름을 바꾸면 다른 볼륨이 생성되므로 기존 프로젝트 이름을 유지하세요.
MySQL 호스트 포트는 기본 `127.0.0.1:3307`이며 외부 네트워크에 공개하지 않습니다.
기존 볼륨의 비밀번호는 `.env` 수정만으로 바뀌지 않습니다. 인증 실패 시 기존 계정을 확인하세요.
`DB_USER=root`는 이전 로컬 구성 호환용이며 운영에서는 별도 최소 권한 계정을 사용하세요.
이 구성은 별도 계정을 자동 생성하지 않습니다. 기존 `ai-results` SQLite 볼륨은 삭제하지 않습니다.
일반 `docker compose down`은 볼륨을 유지하지만 **`docker compose down -v`는 결과 볼륨을
삭제하므로 사용하지 마세요.** 볼륨 보존과 별도로 운영 백업이 필요합니다.

## 실험적 수집/SSE

최종 공개 계약이 아닌 개발용 기능입니다. 기본 실행에서는 다음 경로가 등록되지 않아 404입니다.

- `POST /experimental/analysis/collect/stream`
- `GET /experimental/analysis/jobs/{job_id}`

실험 경로 등록에는 `ENABLE_EXPERIMENTAL_COLLECTION=1`과 명시적 `DATA_SERVER_BASE_URL`이 필요합니다.
새 SSE는 팀원 분석기를 사용하고 v0.5 결과를 반환합니다. 누락 근거는 null로 처리하며
`ALLOW_LEGACY_CRAWLER_DEFAULTS`는 더 이상 사용하지 않습니다. 토큰 전송은 HTTPS만 허용합니다.
실제 이벤트 계약 확인 전 운영에서 켜지 마세요.
세부 입력 매핑·이벤트·연결 중단 한계는 [통합 준비 문서](docs/integration-preparation.md)에 정리돼 있습니다.

## 구조와 기존 파일

- main.py: 기존 ASGI 진입점과 분석 import 호환
- app/api/: HTTP 요청·응답 DTO와 라우팅
- app/factory.py: 전용 결과 저장소 초기화와 선택적 크롤러 client 수명 관리
- app/repositories/mysql_jobs.py: 기본 MySQL 작업/결과 저장소
- app/repositories/analysis_jobs.py: 저장소 인터페이스와 테스트·과거 파일 조회용 SQLite 구현
- app/contracts/, app/integrations/: 크롤러 SSE 계약과 수신 어댑터
- app/services/collection_stream.py: 수집 진행, 분석 중 heartbeat, 저장 후 result
- app/services/data_analysis.py, app/scoring/meta_scorer.py: 공식 v0.5 분석·저장과 RTI 계산
- ai/analysis.py: 과거 스크립트 호환용 비운영 분석 모듈
- app/analyzers/: 공식 v0.5 분석 알고리즘 (이번 제거 작업에서 변경 없음)
- ai/text_analyzer.py, behavior_analyzer.py, network_analyzer.py: 과거 스크립트 참고용 비운영 분석기
- ai/sentiment_client.py: 기존 선택적 Google Cloud 감성 분석
- tests/: HTTP·입력 검증·점수 회귀 검사
- scripts/, db/, 기존 repository/crawler/product 서비스: 과거 개발 참고용 보존 (새 결과 DB와 별개)
- app/core/database.py, app/worker/consumer.py, worker/redis_consumer.py: deprecated 안내만 제공

과거 DB 조회 API 5개(/api/internal/ai/...)는 등록을 해제했으며 404입니다.
Data 서버는 상품 ID만 보내던 방식에서 실제 reviews를 보내는 방식으로 전환해야 합니다.
크롤링 참고 도구가 필요하면 requirements-legacy.txt를 별도로 설치합니다.
SQLite 검증 스크립트는 production API 테스트와 별개입니다.

## 과거 Google Cloud 감성 분석 설정

아래 설정은 과거 비운영 분석 모듈의 참고용입니다. 공식 v0.5 API에는 Google 감성 adapter를
자동 연결하지 않으므로 GOOGLE_APPLICATION_CREDENTIALS를 설정해도 공식 분석 점수는 바뀌지 않습니다.
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
