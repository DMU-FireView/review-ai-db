# AI 통합 준비 상태 — v0.5 연동 반영

이 문서는 이전 AI-only/DB 제거 계획보다 우선한다. 같은
codex/modular-project-cleanup 브랜치에서 작업 중이며 공개 API 계약은 미확정이다.

## 현재 구현

- 기존 POST /api/v1/analyze 본문과 점수/사유는 유지한다.
- POST /api/v1/data/analyze와 SSE는 승인된 팀원 분석기 및 v0.5 평면 결과를 사용한다.
  최신 계약·인증 설명은 [Data AI v0.5 연동](data-ai-v05-integration.md)을 우선한다.
- 요청과 결과를 MySQL ai_analysis_jobs 테이블에 저장한다.
- DB 커밋 성공 후에만 최종 JSON 또는 SSE result를 반환한다.
- X-Analysis-Job-ID는 AI 저장 작업 ID다. 크롤러의 job_id와 별개이며 멱등 키가 아니다.
- 기본 저장소는 MySQL로 전환했다. SQLite 구현은 격리 테스트·과거 파일 조회용으로 남긴다.
  기존 팀 테이블을 변경하거나 SQLite 데이터를 자동 이관하지 않는다.
- Docker의 기존 ai-db-data 볼륨을 재사용한다. 과거 ai-results 볼륨도 삭제하지 않는다.
  docker compose down -v는 결과를 삭제하므로 사용하지 않는다.

## 이전 MySQL 전환 검증 상태

- 로컬 테스트 146개 통과, 실제 MySQL 통합 테스트 1개는 접속 환경 미확정으로 건너뜀.
- Docker Compose 설정 검사와 AI 이미지 빌드 통과. AI 점수 공식·분석 알고리즘은 변경하지 않음.
- 기존 로컬 MySQL은 인증 실패로 저장 검증을 완료하지 못했으며 컨테이너 교체·데이터 삭제는 하지 않음.
- DB 작업은 중단 상태. 새 클라우드 VM 준비 후 새 DB 계정을 설정하고 실행·저장 검증을 재개해야 함.
- 새 볼륨으로 시작하면 빈 DB가 생성된다. 기존 데이터의 자동 복원·이관은 제공하지 않음.

## 실험 API (기본 OFF)

ENABLE_EXPERIMENTAL_COLLECTION=1과 명시적 DATA_SERVER_BASE_URL로 활성화한다.
인증 토큰은 X-Internal-Token으로 전송하며 HTTPS가 필요하다. 실제 이벤트 샘플 확인 전 운영 공개 금지.

- POST /experimental/analysis/collect/stream
  - 임시 요청: platform, product_id, limit(1~500), 선택 job_id. product_key 지정은 422다.
  - 서버 발급 작업 ID는 응답 헤더 X-Analysis-Job-ID와 progress/error에 실린다.
  - progress / heartbeat / result / error 이벤트를 사용한다.
  - result는 v0.5의 platform/product_id/review_count/results와 평면 점수·사유 코드 배열이다.
- GET /experimental/analysis/jobs/{job_id}
  - 저장된 상태·결과 조회용 임시 경로. 원본 입력은 반환하지 않는다.

ALLOW_LEGACY_CRAWLER_DEFAULTS 플래그와 과거 기본값 매핑은 더 이상 실행 경로에서 사용하지 않는다.
정규화 리뷰의 ID·본문·rating·written_at을 새 계약에 전달한다. 원본 수집 데이터는 DB에 보존한다.
본문 외 행동 근거를 생성하지 않는다. 부족한 행동·비교 근거의 점수는 null이다.

## 팀원 코드와의 차이

출처: DMU-FireView/review-ai-new 커밋 bb2dd83b1ecd63947971363af3dd81271b566cf2.
contracts/crawler.py, contracts/stream.py, integrations/crawler_stream.py는 해당
스키마·SSE 디코더/수신기에서 가져와 import 경로와 URL 인코딩을 조정했다.
이후 사용자 승인으로 c48b7e566bf8e5d4c832c2fcad64da4406af707e의 분석기·점수 service·
NormalizedTextSimilarityAdapter·RTI 계산기를 새 Data API와 SSE에 연결했다.
기본 가중치는 .5/.3/.2이며 가용 신호만 재정규화한다. 80 이상 safe를 유지한다.
기존 ai/*.py 평가는 호환 API 전용으로 남기며 서로 다른 계산 경로를 혼합하지 않는다.

## 연결 종료·복구 범위

- 크롤러 done 누락/수량 불일치/다른 상품/충돌 중복은 성공 분석으로 처리하지 않는다.
- 동일 원본 키(platform, product_id, review_id)의 동일 리뷰는 중복 제거한다.
- 수집 중 받은 원본은 DB에 보관한다. 연결 중단은 FAILED로 기록한다.
- 분석 단계에서 연결이 끊겨도 이미 시작한 연산은 프로세스가 살아 있는 동안 저장까지 진행한다.
- 분석 중에도 heartbeat를 보낸다. 이는 총 처리 시간 예측이나 영구 작업 큐가 아니다.
- 프로세스 강제 종료 시 RUNNING 작업은 그대로 남는다. 자동 재개/재전송/멱등 요청은 미구현이다.
  저장된 입력/결과로 운영자가 복구할 수 있지만, 결과 유실 방지의 완성 단계는 아니다.
- SSE 전송 성공은 수신 확인을 뜻하지 않는다. 결과 재조회 계약과 보존 기간을 합의해야 한다.
- MySQL 볼륨 장애 대비 백업·복원과 접근 통제는 운영 배포 전 필수다.
- 크롤러 재연결은 순서 기반 best-effort라 기본 0회다. 임의로 켜서 정확한 재개를 보장하지 않는다.

## 합의 후 해야 할 일

1. Data 측에 새 API 경로·평면 필드·오류·헤더를 전달하고 실제 샘플·HTTPS 주소로 연동 검증.
2. MySQL 계정·백업, 결과 보존/삭제, 중복 요청·재시작 복구 정책 확정.
3. 실크롤러·Spring 연동 및 긴 분석 timeout 검증.
4. main 충돌 해결과 PR 설명 갱신. 기존 PR의 DB 제거 설명은 현재 상태와 다르다.

아래는 2026-09-09의 과거 검증 기록이며 현재 MySQL 연결 검증 결과가 아니다.

- pytest: 42개 통과 (기존 RTI 회귀, 실제 로컬 TCP HTTP, mock SSE, 저장 실패/연결 종료 포함).
- git diff --check 통과, ai/ 평가 파일 변경 없음.
- docker compose config --quiet 통과.
- Docker 빌드는 Linux 엔진 파이프 부재로 미실행. 새 이미지 실행/볼륨 검증은 남아 있다.
- commit/push/PR 변경 및 main 충돌 해결은 이번 작업에서 수행하지 않았다.
