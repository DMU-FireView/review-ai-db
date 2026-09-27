<!-- 독립 AI 서비스 전환의 분석·변경·보존 범위를 기록한다. -->
# 독립 AI 서비스 전환

> 과거 전환 기록입니다. 2026-09-09 회의 반영으로 AI 자체 결과 DB를 추가하고
> 수집/SSE 통합을 준비 중입니다. 현재 기준은 [통합 준비 상태](integration-preparation.md)입니다.

## 기존 구조 분석

- main.py → app/factory.py → 시작 시 MySQL DDL → app/api/routes.py의 DB 조회 API.
- app/repositories/: 상품 식별자/URL과 리뷰를 MySQL에서 조회.
- app/analyzers/heuristic.py: ai/의 세 분석기를 결합해 RTI 산정.
- ai/: 텍스트/행동/네트워크 규칙, Google 감성 분석, 정규화, SQLite 결과 조회.
- app/services/product.py: 요약·추이·위험 보고서 응답 조립.
- worker/: Redis BLPOP 수신 골격. 실제 분석·저장 파이프라인은 미연결.
- scripts/: 크롤링, 변환, SQLite 적재/점수 저장, Worker 시뮬레이션, 샘플 생성.
- db/: MySQL 초기화와 SQLite 스키마/시드, ERD 참고 자료.
- docker-compose.yml: 기존 MySQL/Redis만 실행하며 AI 컨테이너가 없었음.
- requirements.txt: API/AI와 크롤링/인프라 패키지가 혼재.
- .github/workflows/ci.yml: SSH git pull 후 DB/Redis .env 생성, 구형 docker-compose 호출.
- .gitignore: .env, 캐시, 일부 생성물 제외.
- tests/: 이전 계약 검사는 AST 경로·필드 비교만 수행.
- docs/, api-spec/: 과거 팀 설계 기록. 현재 실행 계약은 README와 OpenAPI 참조.
- artifacts/, .pptx_build/, 프레젠테이션 파일: 별도 사용자 작업으로 보존.

## 변경과 deprecated 범위

AI 시작/요청 경로에서 DB와 Redis 의존성을 제거했다.
DB_HOST/PORT/HOST_PORT/USER/PASSWORD/NAME과 Redis 설정은 AI 실행에 불필요하다.
pymysql과 redis import 및 실행 패키지를 제거했다.
app/core/database.py와 두 Worker 진입점은 이관 안내 오류를 내는 deprecated 모듈이다.
상품/review repository, 크롤러, 상품 보고서 함수와 scripts/, db/는 참고용으로
보존하지만 production 경로에서 사용하지 않는다. Docker 이미지에서도 DB/큐/
크롤러 모듈을 제외한다. requests/playwright는 requirements-legacy.txt로 분리했다.

기존 5개 /api/internal/ai/... 경로는 상품 ID만으로 DB 조회하는 계약이므로
등록 해제(404)했다. Data 서버는 /api/v1/analyze에 reviews를 전달해야 한다.
기존 DTO와 main의 분석 import는 로컬 도구 호환 목적으로 보존한다.
파일을 통째로 삭제하지 않았으며 새 역할에 맞게 진입점/설정만 변경했다.

## 알고리즘 보존

calculate_text_score, calculate_behavior_score, calculate_network_score,
analyze_sentiment 구현 파일은 수정하지 않았다.
통합 함수는 ai/analysis.py로 옮기고 이전 모듈은 re-export한다.
가중치 0.4/0.35/0.25, Python round, 50/80 경계, 사유 순서,
input_features 문자열 변환을 유지했다.
account_age_days는 허용하지만 점수 요소로 사용하지 않는다.
이전 DB 경로는 image_count=0, quality_score=0.5를 강제로 제공했다.
새 HTTP에서 실제 다른 특성을 보내면 같은 공식이어도 결과가 달라질 수 있다.
Data 서버가 파생 신호를 제공하며 AI 서버는 수집·저장·작업 상태 관리를 하지 않는다.

## 테스트와 남은 결정

pytest 22개 통과: health, 단건/다건, 빈 배열/누락/잘못된 범위,
실제 세 분석기 호출, 점수 경계, Python 반올림, Google 보조 사유,
account_age_days 비사용, 18개 입력 조합 비교, 기존 API 종료,
실제 Uvicorn TCP health/분석 요청.
pip check와 Compose config 통과. 테스트 라이브러리 deprecation warning 2개.
Docker Linux 엔진 시작 후 이미지 build와 컨테이너 up/ps/logs 검증도 통과했다.
컨테이너는 healthy(재시작 0회), health/analyze HTTP 200, 예제 RTI 88/safe로 확인했다.

팀 결정: Data 서버 계약 전환 시점, 호출 인증/접근 제어, 최대 배치 크기/
요청 시간 제한, Google 감성 분석 사용 여부, VM 생성과 GitHub Secrets,
비대화식 git/sudo 설정. PostgreSQL과 작업 오케스트레이션은 Data 서버 책임이다.
로컬 Docker 실행을 검증했으며 Azure 배포나 기존 인프라 중지는 수행하지 않았다.
