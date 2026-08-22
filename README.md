# Re:view AI + DB

리뷰 신뢰도(RTI)를 계산하고 Spring Boot 백엔드에 내부 API를 제공하는
FastAPI 서비스입니다.

## 연동 계약

- 실행 진입점: `main:app`
- 기본 포트: `8000`
- API prefix: `/api/internal/ai`
- 데이터베이스: MySQL
- 비동기 작업 큐: Redis (`review_analysis_queue`)

현재 백엔드가 사용하는 API 경로는 다음과 같습니다.

| Method | Path |
|---|---|
| POST | `/api/internal/ai/products/product-list` |
| POST | `/api/internal/ai/reviews/product-detail` |
| POST | `/api/internal/ai/products/rti-trend` |
| POST | `/api/internal/ai/reviews/report` |
| POST | `/api/internal/ai/products/risk-report` |

요청·응답 모델의 상세 내용은 실행 후 `/docs`에서 확인할 수 있습니다.

## 로컬 실행

1. `.env.example`을 `.env`로 복사하고 로컬 접속 정보를 입력합니다.
2. 의존성을 설치합니다.
3. MySQL과 Redis를 실행한 뒤 API 서버를 시작합니다.

```powershell
python -m pip install -r requirements.txt
docker compose up -d
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

`main.py`를 직접 실행해도 포트 `8000`으로 동작합니다.

## 주요 구조

```text
app/
  api/          기존 내부 API route와 요청·응답 DTO
  core/         환경설정과 MySQL 연결
  services/     분석·통계·리포트 처리 순서
  analyzers/    규칙 기반 및 외부 AI 모델 adapter
  crawlers/     네이버 Playwright crawler adapter
  repositories/ 상품·리뷰·점수 저장소
  worker/       Redis consumer 구현
ai/          기존 RTI 계산 알고리즘
api-spec/    백엔드 연동 명세
data/        입력 예제와 정규화 샘플
db/          MySQL 스키마와 시드
docs/        설계·협업 문서
output/      연동용 샘플 응답과 로컬 생성 결과
scripts/     크롤링·적재·검증 도구
tests/       API 계약·분석 유틸·SQLite 조회 회귀 검사
worker/      기존 worker 실행 경로 호환 진입점
main.py      기존 `main:app` 호환 ASGI 진입점
```

로컬 SQLite DB와 전체 분석 결과는 실행 산출물이므로 Git에 포함하지
않습니다. 백엔드 연동 확인용 `output/*_sample.json`만 추적합니다.

## 환경변수

기존 백엔드 및 배포 설정과의 호환을 위해 환경변수 이름을 유지합니다.

| 이름 | 기본값 | 용도 |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | MySQL 호스트 |
| `DB_PORT` | `3306` | MySQL 포트 |
| `DB_USER` | `root` | MySQL 사용자 |
| `DB_PASSWORD` | `0000` | MySQL 비밀번호 |
| `DB_NAME` | `review_system` | MySQL 데이터베이스 |
| `DB_HOST_PORT` | 없음 | Docker가 노출할 MySQL 포트 |
| `REDIS_HOST` | `localhost` | Redis 호스트 |
| `REDIS_PORT` | `6379` | Redis 포트 |
| `REDIS_PASSWORD` | 없음 | Redis 비밀번호 |

## 주의

- API 서버 시작 시 필요한 MySQL 테이블을 `CREATE TABLE IF NOT EXISTS`로
  확인합니다. 기존 데이터를 삭제하거나 시드를 강제로 넣지 않습니다.
- `worker/redis_consumer.py`는 현재 큐 메시지 수신 흐름의 뼈대입니다.
  실제 크롤링·분석·저장 파이프라인을 연결하기 전까지 운영 처리기로
  간주하지 않습니다.
