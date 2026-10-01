<!-- 기존 운영 구조를 보존한 2차 AI 런타임 통합의 비교·실측·배포 조건을 기록한다. -->
# AI 런타임 2차 통합 검증 — 2026-10-02

2차 검증 시점 상태: **로컬 통합·전체 테스트 완료, 미배포·미커밋**.
해당 검증 단계에서 Azure 배포, commit/push/merge, 모델 재학습, Groq/LLM 연동은 수행하지 않았다.
이후 코드 확정 단계에서는 별도 feature 브랜치의 commit/push와 main 대상 PR 생성까지만 승인되었다.
본 보고서는 운영 배포나 PR 병합 완료를 의미하지 않는다.
모델 파일은 Git/이미지에 넣지 않았고 로컬 `.env`와 기존 실행 중인 API/DB도 변경하지 않았다.
검증 종료 후 전용 컨테이너·네트워크·tmpfs 테스트 DB는 정리했다. 임시 DB 데이터는 소멸했고
측정 JSON은 보존했다. 기존 review-ai/review_ai_db와 영구 볼륨은 그대로이며 검증 이미지는 로컬 재사용용으로 남겼다.

검증 데이터: [측정 JSON](review-ai-runtime-integration-20261002.json).
1차 인수인계 검증 기록은 로컬에 별도 보존하며 이번 결과와 구분한다. 해당 로컬 기록은 이번 PR에 포함하지 않는다.

## 1. 두 저장소 main 비교와 선택

양쪽 origin/main을 fetch해 비교했다. 현재 review-ai-db는 main이며 HEAD와 origin/main의 차이는 0/0이었다.
Git 이력 병합이 아니라 검증된 런타임 파일만 로컬 코드에 통합했다.

- 운영 기준: FireViewLab/review-ai-db `eaa9f8776f6ce195576257ec923f6b9f200b25ee`.
- AI 기준: FireViewLab/review-ai-new `ff3c149697370e3891a75c11be74efb9ba735196`.
- 조직 이름은 FireViewLab로 문서에 반영했다. 로컬 origin의 기존 DMU-FireView URL은 이번에 변경하지 않았다.

| 항목 | review-ai-db 기존 main | review-ai-new main | 통합 선택 |
| --- | --- | --- | --- |
| 진입점 | main:app → app.factory | app.main:app | 운영 진입점/factory 유지 |
| health | GET /health | analysis router 중심 | 기존 health 유지, 모델 로드 없음 |
| 운영 분석 경로 | POST /api/v1/data/analyze | /analysis 계열 | 기존 경로·요청 유지, 새 경로 추가 안 함 |
| 내부 인증 | X-Internal-Token, REQUIRE_INTERNAL_TOKEN | 운영 저장/인증 구조와 별개 | 기존 인증 유지 |
| 결과 보관 | MySQL ai_analysis_jobs JSON | 분석 결과 반환 중심 | 기존 MySQL 저장/트랜잭션 유지 |
| 분석 호출 | 별도 team_analysis + mapper | API/SSE의 _analyze가 하위 분석 함수 직접 호출 | 공통 analyze_reviews로 통합 |
| P_text | 과거 규칙 점수 | 최종 로컬 KoELECTRA | 검증된 모델 런타임 적용 |
| 행동·네트워크 | 이전 분석 구현 | 최종 행동·Hybrid A 네트워크 | 검증된 구현 그대로 적용 |
| 결과 | 숫자 누락 null, 80/50 등급 | 숫자 누락 -1, 70/40 등급 | 검증된 신규 계약 적용, Data 소비자 확인 필요 |
| SSE | 기본 OFF 실험 경로, 저장/heartbeat/재조회 | crawler SSE + 분석 result | 기존 운영용 gateway/SSE 수명·저장 흐름 유지 |
| 배포 | Docker/Compose/MySQL/GitHub Actions | pyproject 기반 ML optional dependencies | 운영 Docker/Actions 유지, CPU ML 의존성 추가 |

원본 new의 API/SSE는 analyze_reviews 대신 _analyze에서 analyze_product_reviews와 serializer를 호출한다.
1차에는 사용자 선택에 따라 차이를 TODO로 남겼지만, 이번 운영 통합에서는 기존 API/SSE의 공통 평가 함수가
analyze_reviews를 호출하게 했다. 원본 new 저장소의 main/config/API는 수정하거나 통째로 가져오지 않았다.

## 2. 통합 구조

```text
main:app → create_app (기존 lifespan·인증·MySQL)
  ├─ GET /health                         모델 로드 안 함
  ├─ POST /api/v1/data/analyze ─────────┐
  └─ 실험 수집/SSE → collection_events ┤
                                      ↓
                          evaluate_data_and_store
                                      ↓
                          analysis.analyze_reviews
                                      ↓
               KoELECTRA / P_behavior / P_network → RTI
                                      ↓
                        공통 Result Contract serializer
                                      ↓
                     MySQL complete → JSON 또는 SSE result
```

Python analyze_reviews 직접 호출은 순수 분석이며 DB 저장은 운영 평가 계층에서 담당한다.
API와 SSE는 동일한 계산·직렬화·저장 경로를 사용한다. 저장 실패 시 성공 결과를 내보내지 않는다.
기존 수집 중 입력 보관, 중복 리뷰 처리, heartbeat, 오류 기록, 분석 시작 후 연결 중단 시 저장 동작을 보존했다.

모델은 local_files_only로 읽는다. lru_cache(maxsize=1)와 RLock이 첫 로드·추론을 직렬화한다.
캐시는 프로세스 단위이므로 worker를 늘리면 모델 메모리도 중복된다. Docker의 worker는 1로 명시했다.
코드의 CUDA 사용 가능 여부 선택/CPU fallback은 원본 그대로다. 이번 실제 테스트는 CPU만 사용했다.
기본 이미지는 CPU 전용 torch이므로 GPU 운영은 별도 의존성/이미지 검증이 필요하다.

## 3. 변경 파일과 이유

### 분석 런타임

- 추가: `app/analyzers/p_text.py`, `app/schemas/__init__.py`, `app/schemas/analysis.py`.
  최종 KoELECTRA 로더·점수 변환과 평면 결과 계약/serializer를 가져왔다.
- 수정: `app/analyzers/behavior.py`, `app/analyzers/network.py`, `app/integrations/similarity.py`,
  `app/scoring/meta_scorer.py`, `app/services/analysis.py`.
  new main의 검증된 분석 구현을 적용했다. analysis.py 마지막 오프라인 호환 import 외에는 원본과 같다.
- 수정: `app/services/team_analysis.py`.
  기존 import를 깨지 않도록 공통 분석 함수·타입의 호환 재노출 모듈로 남겼다.
- 추가: `app/services/legacy_analysis.py`.
  과거 main export/정규화·저장 스크립트용 analyze_reviews 및 prepare_review_input을 분리 보존했다.
  운영 분석 경로는 이 과거 점수 함수를 호출하지 않는다.
- 수정: `app/services/data_analysis.py`, `app/contracts/data_ai_v05.py`,
  `app/integrations/data_ai_v05_mapping.py`.
  기존 요청 검증과 식별자 보존을 유지하면서 공통 진입점·serializer를 사용하도록 연결했다.

P_text, behavior, network, similarity, meta_scorer, schemas/analysis의 정책을 임의로 다시 설계하지 않았다.
기존 text reason 분석은 점수 대체가 아니라 구조화된 이유 생성용으로 남는다.

### Docker·설정

- 수정: `Dockerfile`, `docker-compose.yml`, `.env.example`, `.dockerignore`, `.gitignore`.
- 추가: `requirements-ml.txt`, `docker-compose.validation.yml`.

CPU 의존성, 외부 모델 읽기 전용 bind mount, worker 1, OMP/MKL 2 스레드를 추가했다.
모델 호스트 경로가 없으면 Compose가 빈 폴더를 자동 생성하지 않고 기동 실패한다.
validation override는 별도 이미지/컨테이너·무작위 로컬 포트·임시 tmpfs DB·합성 토큰만 쓰는 로컬 검증용이다.
실행한 Compose v5.1.1에서 검증했다. 이 override는 !override를 지원하는 Compose가 필요하며 운영 배포에 사용하지 않는다.

### 테스트·검증 도구

- 수정: `tests/test_data_ai_v05.py`, `tests/test_persisted_stream.py`, `tests/test_mysql_jobs.py`,
  `tests/test_http_server.py`.
- 수정: `tests/team_core/test_analysis.py`, `test_behavior.py`, `test_meta_scorer.py`, `test_network.py`.
- 추가: `tests/conftest.py`, `tests/test_integrated_runtime.py`, `tests/team_core/conftest.py`,
  `tests/team_core/test_ptext_runtime.py`, `test_behavior_network_pipeline.py`, `test_hybrid_network.py`.
- 추가: `scripts/validate_integrated_runtime.py`.

단위 테스트는 모델 없는 결정적 fixture를 쓰고 실제 가중치 검증은 별도 smoke로 수행한다.
초기 전체 테스트의 12개 실패는 이전 P_text/80·50/네트워크 기대값이었다.
새 런타임 정책을 바꾸지 않고 해당 기대값과 비교 가능한 본문 fixture를 정리했다.
인증·저장 실패·크롤러 오류·연결 중단 테스트를 삭제하지 않았다.

### 문서

수정: `README.md`, `docs/README.md`, `docs/data-ai-v05-integration.md`,
`docs/integration-preparation.md`, `docs/azure-ai-deployment.md`.
추가: 본 보고서와 측정 JSON.

기존 1차 검증 기록, 팀원 원문, 관련 없는 미추적 산출물은 그대로 보존했다.

## 4. 유지한 운영 기능

다음 파일은 변경하지 않았다.

- `main.py`, `app/factory.py`, `app/api/routes.py`: 기존 진입점·health·lifespan.
- `app/core/internal_auth.py`, `app/core/crawler_settings.py`: 내부 인증·토큰 TLS 전송 정책·기존 env 이름.
- `app/repositories/mysql_jobs.py`: 기존 테이블/JSON 컬럼/커밋·롤백·작업 상태.
- `app/api/data_analysis.py`, `app/api/collection.py`, `app/services/collection_stream.py`:
  경로·요청·job header·수집/SSE·오류/저장 정책.
- `.github/workflows/ci.yml`: 기존 테스트→SSH→Compose→health 재시도/실패 로그 배포 구조.

MySQL은 그대로 사용하며 SQLite fallback을 추가하지 않았다. SQLite는 기존 테스트/오프라인 용도로만 남는다.
JSON 컬럼은 신규 -1 숫자와 null level을 그대로 저장하므로 DB migration은 필요하지 않았다.
기존 MySQL 볼륨, 팀 테이블, 저장된 작업을 초기화/삭제/재계산하지 않았다.
retired legacy endpoint `POST /api/v1/analyze`는 계속 404다.

## 5. 결과 계약과 호환성 주의점

신규 결과는 platform/product_id/review_count/results와 리뷰별
review_id/rti/level/text_score/behavior_score/network_score/reasons만 반환한다.
숫자 누락은 -1이고 level만 null을 허용한다. reasons는 SOURCE_CODE 접두사 문자열이며 중복을 제거한다.
RTI는 50/30/20, 가용 신호만 재정규화, 소수점 한 자리 반올림이다. safe는 70 이상, warn은 40 이상이다.
이 기준은 검증된 new main 기준이며 이번 통합에서 새로 튜닝한 것이 아니다.

| text / behavior / network | 기대 RTI | 검증 |
| --- | --- | --- |
| -1 / 60 / 80 | 68.0 | unavailable text 제외 |
| 85 / -1 / 76 | 82.4 | unavailable behavior 제외 |
| 85 / 60 / -1 | 75.6 | unavailable network 제외 |
| -1 / -1 / -1 | -1, level=null | 모든 신호 없을 때만 최종 unavailable |
| 0 / -1 / -1 | 0, danger | 실제 0은 정상 점수로 포함 |

위 계산 회귀와 서비스/API/저장/SSE 조합 테스트가 통과했다. 내부 dataclass의 누락 None은
외부 serializer에서 -1로 변환하며 외부 숫자 점수에 null이나 임의의 0을 사용하지 않는다.

주의:

1. **신규 결과와 과거 저장 결과는 구분한다.** 실험 GET job 조회는 과거 JSON을 그대로 반환한다.
   과거 null 점수/80·50 등급/이전 reasons를 자동 변환하지 않았다. 기본 OFF를 유지하며
   과거 조회까지 새 계약으로 강제하지 않는다. 필요 시 버전 구분/이관 정책을 별도 합의해야 한다.
2. 기존 운영 요청의 rating/written_at은 원본 JSON에 보관하지만 행동 증거로 만들어 넣지 않는다.
   구매 인증·안정적인 사용자 ID·계정 생성일·작성 이력이 없는 현 입력에서는 behavior_score=-1이 정상이다.
   Python 진입점의 행동 근거 입력과 분석기는 테스트했지만 운영 입력 확장은 Data와 별도 협의가 필요하다.
3. 이전 운영 응답과 null/등급 경계/rounding/reasons/review_count 요구가 다르다.
   Data 소비자의 sentinel·등급·코드 처리 확인 없이 그대로 운영 배포하지 않는다.
4. /health는 프로세스 생존 확인이다. 모델 lazy loading과 충돌하지 않지만 모델 readiness를 보장하지 않는다.
   가중치 오류가 첫 분석에서 -1로 처리되므로 배포 smoke는 text_score!=-1까지 확인해야 한다.

## 6. 전체 검증 결과

| 검증 | 결과 |
| --- | --- |
| Windows 전체 pytest + 임시 MySQL | 327 passed, 2 deprecation warnings, 3.70s |
| Docker Linux 동일 이미지 전체 pytest + 임시 MySQL | 327 passed, 1 deprecation warning, 7.05s |
| Compose config / build / up | 성공 |
| 컨테이너 health | healthy, OOMKilled=false |
| 외부 모델 읽기 전용 마운트 | 확인, 컨테이너 uid 10001에서 로드 성공 |
| CPU torch | 2.8.0+cpu, CUDA version=None, NVIDIA package 없음 |
| 실제 HTTP GET /health | 200, status=ok |
| 실제 HTTP POST 공식 API | 토큰 없음 401 / 합성 토큰 200 |
| 실제 HTTP 결과 → MySQL 재조회 | DONE, JSON 값 동일 |
| retired legacy endpoint | 404 |
| API / SSE / MySQL 결과 | 동일 |
| 모델 캐시 | 각 smoke 프로세스 misses=1, currsize=1 |
| 실제 가중치 없는 경로 | health 200 / 분석 200, 네 점수 -1·level null, MySQL 값 동일 |
| 모델 가중치 SHA256 | e7677366e93afef3f26890c81fffa62e7a1db96f24cba55a19cdeaf9efb5f354 |
| 모델 Git/이미지 포함 | 없음 |
| startup 로그 | 오류 없음 |
| git diff --check | 통과 |

PR 준비 직전 재검증에서도 Windows 327 passed(3.98s), 동일 CPU 이미지의 Docker Linux
327 passed(8.18s)를 확인했다. 양쪽 모두 전용 임시 MySQL을 사용했고 Compose config와
git diff --check도 통과했다. 분석 런타임 정책은 기존 검증 상태와 동일하여 모델 smoke는 중복 실행하지 않았다.

SSE는 기존 CrawlerStreamClient와 실제 모델·MySQL을 사용하고 HTTPS Data 전송만 httpx.MockTransport로 대체했다.
progress 3회 후 result를 받았으며 API=stream result=저장값=인증 재조회 값이 같았다.
이는 실제 Data 서버/Caddy/프록시 왕복 검증을 의미하지 않는다.
Pytest의 경고는 FastAPI/Starlette TestClient 의존성 deprecation이며 기능 실패가 아니다.
추가 오류 경로 검증은 실제로 없는 모델 경로를 지정해 수행했다. 이 별도 진단 프로세스의
FileNotFoundError 로그는 예상한 unavailable 처리이며 실행 중인 API startup 오류가 아니다.

기본 운영 Swagger:

- GET /health
- POST /api/v1/data/analyze

ENABLE_EXPERIMENTAL_COLLECTION=1인 검증 환경에서만 다음이 추가된다.

- POST /experimental/analysis/collect/stream
- GET /experimental/analysis/jobs/{job_id}

### CPU 성능·메모리 실측

AI 검증 컨테이너에 2 CPU quota·4 GiB memory limit를 실제 적용했다.
Docker Desktop Linux, Python 3.12, torch CPU, OMP/MKL 2, worker 1 환경이다.
별도 smoke Python 프로세스의 /proc RSS/HWM을 측정했으며 두 번째 FastAPI worker를 띄운 것은 아니다.

| 항목 | 기본 리뷰 smoke | 긴 리뷰 포함 재실행 |
| --- | --- | --- |
| 모델 로드 전 RSS | 225.73 MiB | 226.05 MiB |
| 모델 로드 후 RSS | 349.05 MiB | 349.31 MiB |
| 로딩 시간 | 1.5481s | 1.5302s |
| 리뷰 1건 추론 | 0.7861s | 0.0596s |
| 리뷰 3건 분석 | 0.1245s | 0.1356s |
| 리뷰 10건 분석 | 0.4155s | 0.4342s |
| 짧은 리뷰 100건 분석 | 4.4714s | 4.4343s |
| 256토큰 리뷰 100건 분석 | 미실행 | 29.2896s |
| 프로세스 최대 RSS | 690.67 MiB | 721.56 MiB |

가중치 메모리가 mmap으로 연결되어 로드 후보다 실제 첫 추론 뒤 RSS가 커진다.
1건 시간 차이는 초기 커널/페이지 상태 영향으로 볼 수 있으며 반복 SLA로 일반화하지 않는다.
긴 합성 리뷰는 source 1962토큰을 실제 설정 max_length=256으로 잘라 분석했다.
검증 중 MySQL 컨테이너 메모리는 별도 관측 약 575 MiB였고 DB에는 4 GiB 제한을 적용하지 않았다.

판단: **2 vCPU / 4 GiB / worker 1은 초기 배포 후보로 타당**하다.
다만 Docker CPU quota는 실제 Azure VM과 같지 않고 전체 VM(OS/DB/다른 서비스)의 4 GiB 예산을 검증한 것은 아니다.
동시 요청, 최대 500건, 장시간 부하와 프록시 timeout은 추가 검증이 필요하다.

## 7. Azure 환경변수·모델 마운트

기존 환경변수 이름을 제거하거나 바꾸지 않았다. 로컬 .env를 실제 운영 값으로 수정하지도 않았다.

| 환경변수 | 향후 운영 준비 |
| --- | --- |
| DB_HOST / DB_PORT | Compose 내부 ai-db / 3306, 로컬 Python은 별도 호스트/포트 |
| DB_USER / DB_PASSWORD / DB_NAME | 기존 데이터에 유효한 계정, 운영 최소 권한 권장 |
| DB_HOST_PORT | 기존 로컬 DB 포트, 기본 3307 |
| REQUIRE_INTERNAL_TOKEN | 운영 1 |
| INTERNAL_TOKEN | 서버 간 비밀 토큰, Git/이미지/공개 문서에 넣지 않음 |
| DATA_INTERNAL_TOKEN | Data 전용 토큰, 없으면 기존 INTERNAL_TOKEN fallback |
| DATA_SERVER_BASE_URL | 실험 SSE를 켤 때 확정 HTTPS Data 주소 |
| ENABLE_EXPERIMENTAL_COLLECTION | 기본 0, 계약/실서버 검증 후에만 1 |
| CRAWLER_BASE_URL / CRAWLER_STREAM_TIMEOUT / CRAWLER_MAX_RETRIES | 기존 fallback/timeout/재시도 설정 보존 |
| PTEXT_MODEL_HOST_PATH | VM의 외부 모델 폴더 |
| PTEXT_MODEL_PATH | 컨테이너 내부 모델 폴더 |
| OMP_NUM_THREADS / MKL_NUM_THREADS | 초기 2 |

권장 위치 예시:

```dotenv
PTEXT_MODEL_HOST_PATH=/opt/review-ai-models/ptext-koelectra-v1-2epoch-20260929
PTEXT_MODEL_PATH=/models/ptext-koelectra-v1-2epoch-20260929
```

7개 인수인계 파일(config, inference_config, safetensors, tokenizer, tokenizer_config,
special_tokens_map, vocab)을 폴더에 준비하고 uid 10001의 읽기/경로 탐색 권한을 확인한다.
호스트 폴더→컨테이너 경로로 read_only bind mount하며 모델 파일은 git add 하지 않는다.
HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE/TOKENIZERS_PARALLELISM은 이미지/Compose에 설정했다.

## 8. 남은 배포 TODO

1. Data 팀에 -1·70/40·review_count·SOURCE_CODE reasons·반올림 정책을 공유하고 소비자 호환 확인.
2. 과거 job 조회의 계약 버전/이관 필요 여부 합의. 기존 JSON 재작성은 이번 범위 밖.
3. VM 외부 모델 폴더·해시·읽기 권한 준비. GitHub Actions가 실행되기 전에 .env 모델 경로 설정.
4. 기존 MySQL 계정/볼륨/백업 확인. 신규 분석 결과가 JSON으로 저장되는 것까지 배포 smoke 실행.
5. AI↔Data 실제 HTTPS·토큰·입력 샘플·SSE 종료/재연결/프록시 버퍼링 검증.
6. 긴 리뷰·최대 500건·동시 요청 부하와 CPU 대기, timeout, 메모리 모니터링/운영 상한 결정.
7. /health와 별개로 실제 모델 추론 smoke(text_score!=-1), unavailable 비율/모델 오류 관측 준비.
8. worker 1 유지. 실제 Azure VM에서 DB/OS까지 포함한 메모리 측정 후 배포 사양 확정.
9. 필요 시 행동 근거 입력 계약 확장. 자동 재개/멱등 요청/자동 재전송은 기존 미구현 상태.
10. 검토 승인 후 배포는 별도 요청으로 진행한다. 후속 승인 범위는 feature 브랜치 commit/push와 PR 생성까지이며 merge/deploy는 하지 않는다.

## 로컬 검증 재현

기존 서비스와 충돌하지 않도록 아래는 전용 validation project만 사용한다.
PowerShell에서 모델의 실제 외부 폴더를 지정하고 합성 DB 비밀번호를 사용한다.
기본 Compose만 실행하면 기존 운영 컨테이너 이름과 충돌할 수 있으므로 이 검증 절차와 구분한다.

```powershell
$env:DB_PASSWORD='qa-disposable-password'
$env:PTEXT_MODEL_HOST_PATH='C:/path/to/final-model-folder'
docker compose --env-file .env.example -p review-ai-runtime-check -f docker-compose.yml -f docker-compose.validation.yml config --quiet
docker compose --env-file .env.example -p review-ai-runtime-check -f docker-compose.yml -f docker-compose.validation.yml build
docker compose --env-file .env.example -p review-ai-runtime-check -f docker-compose.yml -f docker-compose.validation.yml up -d
docker cp scripts/validate_integrated_runtime.py review-ai-runtime-check-api:/tmp/validate_integrated_runtime.py
docker exec -e RUN_MYSQL_TESTS=1 -e PYTHONPATH=/service review-ai-runtime-check-api python /tmp/validate_integrated_runtime.py --cpu-threads 2 --max-reviews 100 --include-max-length
docker compose --env-file .env.example -p review-ai-runtime-check -f docker-compose.yml -f docker-compose.validation.yml down
```

이 검증 DB만 tmpfs이므로 종료 시 테스트 데이터가 소멸한다. 운영 ai-db-data 볼륨에는 적용하지 않는다.
RUN_MYSQL_TESTS=1은 실제 운영 DB가 아닌 명시적으로 준비한 전용 DB에만 사용한다.
