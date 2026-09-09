# AI 통합 준비 상태 — 2026-09-09

이 문서는 이전 AI-only/DB 제거 계획보다 우선한다. 같은
codex/modular-project-cleanup 브랜치에서 작업 중이며 공개 API 계약은 미확정이다.

## 현재 구현

- 기존 POST /api/v1/analyze 본문과 점수/사유는 유지한다.
- 요청과 결과를 전용 SQLite ai_analysis_jobs 테이블에 저장한다.
- DB 커밋 성공 후에만 최종 JSON 또는 SSE result를 반환한다.
- X-Analysis-Job-ID는 AI 저장 작업 ID다. 크롤러의 job_id와 별개이며 멱등 키가 아니다.
- SQLite는 내부 저장소 어댑터의 초기 구현이다. 기존 MySQL/SQLite 팀 스키마를
  변경하거나 기존 데이터를 이관하지 않는다. 운영 DB 종류는 별도 합의 대상이다.
- Docker의 ai-results 볼륨은 컨테이너 교체 후에도 유지된다.
  docker compose down -v는 결과를 삭제하므로 사용하지 않는다.

## 실험 API (기본 OFF)

ENABLE_EXPERIMENTAL_COLLECTION=1과 명시적 CRAWLER_BASE_URL로 활성화한다.
인증/호출 주체/최종 경로가 정해질 때까지 운영 공개 금지. 로컬 테스트용이다.

- POST /experimental/analysis/collect/stream
  - 임시 요청: platform, product_id, limit(1~500), 선택 product_key/job_id.
  - 서버 발급 작업 ID는 응답 헤더 X-Analysis-Job-ID와 progress/error에 실린다.
  - progress / heartbeat / result / error 이벤트를 사용한다.
  - result는 현재 AnalyzeResponse(product_id, results)이다.
    팀원 ProductAnalysisResponse와 다르며 호환 완료를 뜻하지 않는다.
- GET /experimental/analysis/jobs/{job_id}
  - 저장된 상태·결과 조회용 임시 경로. 원본 입력은 반환하지 않는다.

크롤러 입력에는 구매 여부, 일일 작성 수, 유사 리뷰 수 등 기존 점수 입력이 없다.
따라서 ALLOW_LEGACY_CRAWLER_DEFAULTS=1을 추가하지 않으면 수집 요청은 503으로 차단한다.
이 플래그는 실험 승인일 뿐 운영 점수 계약 확정이 아니다.

승인한 실험에서는 이미지 개수와 원본 표시 필드를 매핑하고, 나머지는 기존 ReviewInput의
기본값을 그대로 사용한다(구매 unknown, 일일 1건, 유사 0건, quality None).
rating은 현재 점수 계산에 쓰이지 않아 기존 기본값을 유지하며 원본 rating은 DB 입력에 보관한다.
작성자/날짜 누락은 표시용 빈 문자열이다. 원본에는 없는 관측값을 새로 추론하지 않는다.
이 기본값은 실제 관측 근거가 아니므로 운영 사용 전에 반드시 합의한다.

## 팀원 코드와의 차이

출처: DMU-FireView/review-ai-new 커밋 bb2dd83b1ecd63947971363af3dd81271b566cf2.
contracts/crawler.py, contracts/stream.py, integrations/crawler_stream.py는 해당
스키마·SSE 디코더/수신기에서 가져와 import 경로와 URL 인코딩을 조정했다.
점수 service, NormalizedTextSimilarityAdapter, RTI 계산기는 가져오지 않았다.

팀원 코드는 묶음 유사도와 사용 가능 신호를 계산한다.
현재 저장소는 전달받은 similar_review_count와 고정 가중치 .4/.35/.25를 사용한다.
둘은 동등하지 않으며 임의로 혼합하지 않는다. 기존 ai/*.py 평가 파일은 변경하지 않았다.

## 연결 종료·복구 범위

- 크롤러 done 누락/수량 불일치/다른 상품/충돌 중복은 성공 분석으로 처리하지 않는다.
- 동일 원본 키(platform, product_id, review_id)의 동일 리뷰는 중복 제거한다.
- 수집 중 받은 원본은 DB에 보관한다. 연결 중단은 FAILED로 기록한다.
- 분석 단계에서 연결이 끊겨도 이미 시작한 연산은 프로세스가 살아 있는 동안 저장까지 진행한다.
- 분석 중에도 heartbeat를 보낸다. 이는 총 처리 시간 예측이나 영구 작업 큐가 아니다.
- 프로세스 강제 종료 시 RUNNING 작업은 그대로 남는다. 자동 재개/재전송/멱등 요청은 미구현이다.
  저장된 입력/결과로 운영자가 복구할 수 있지만, 결과 유실 방지의 완성 단계는 아니다.
- SSE 전송 성공은 수신 확인을 뜻하지 않는다. 결과 재조회 계약과 보존 기간을 합의해야 한다.
- SQLite 파일/볼륨 장애 대비 백업·복원과 접근 통제는 운영 배포 전 필수다.
- 크롤러 재연결은 순서 기반 best-effort라 기본 0회다. 임의로 켜서 정확한 재개를 보장하지 않는다.

## 합의 후 해야 할 일

1. 최종 분석기/누락 신호 정책, 공개 API 경로·필드·오류·인증 확정.
2. 최종 DB 엔진, 백업, 결과 보존/삭제, 중복 요청·재시작 복구 정책 확정.
3. 실크롤러·Spring 연동 및 긴 분석 timeout 검증.
4. main 충돌 해결과 PR 설명 갱신. 기존 PR의 DB 제거 설명은 현재 상태와 다르다.

이번 검증은 가짜 크롤러와 로컬 DB 기반이며 외부 실서비스 연결/배포가 아니다.

- pytest: 42개 통과 (기존 RTI 회귀, 실제 로컬 TCP HTTP, mock SSE, 저장 실패/연결 종료 포함).
- git diff --check 통과, ai/ 평가 파일 변경 없음.
- docker compose config --quiet 통과.
- Docker 빌드는 Linux 엔진 파이프 부재로 미실행. 새 이미지 실행/볼륨 검증은 남아 있다.
- commit/push/PR 변경 및 main 충돌 해결은 이번 작업에서 수행하지 않았다.
