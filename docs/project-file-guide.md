<!-- 프로젝트 파일을 역할별로 찾을 수 있도록 정리한 안내 문서이다. -->

# 프로젝트 파일 역할 안내

> 2026-09-08: 일부 모듈은 참고용으로 보존됩니다. 현재 실행 구조는 README.md와 ai-service-migration.md를 기준으로 합니다.

## 실행 애플리케이션

- `main.py`: Azure 배포와 기존 실행 명령이 사용하는 `main:app` 진입점
- `app/api/`: Spring Boot 연동 라우트와 요청·응답 DTO
- `app/core/`: 환경변수와 MySQL 연결·초기화
- `app/services/`: 분석 실행과 상품 통계·보고서 조립
- `app/repositories/`: 상품·리뷰·RTI 저장소 접근
- `app/analyzers/`: 현재 규칙 기반 분석과 향후 모델 adapter
- `app/crawlers/`: 네이버 Playwright crawler adapter
- `app/worker/`: Redis queue consumer 구현
- `worker/redis_consumer.py`: 기존 Worker 실행 명령을 보존하는 호환 진입점

## 분석 알고리즘

- `ai/text_analyzer.py`: 리뷰 본문 신뢰 점수
- `ai/behavior_analyzer.py`: 작성 행동 신뢰 점수
- `ai/network_analyzer.py`: 유사성·네트워크 신뢰 점수
- `ai/sentiment_client.py`: 선택적 Google Cloud 감성 분석
- `ai/normalizer.py`: 원본 리뷰 공통 형식 변환
- `ai/rti_scoring.py`: 정규화 리뷰 일괄 RTI 계산
- `ai/rti_result_mapper.py`: 저장된 점수를 API 분석 결과로 변환
- `ai/rti_score_repository.py`: 로컬 SQLite RTI 조회
- `ai/reason_utils.py`: 판단 사유 표시용 가공

## 운영·개발 도구

- `scripts/crawl_*.py`: 네이버 리뷰 수집
- `scripts/analyze_*.py`: 크롤링 결과와 네트워크 후보 분석
- `scripts/convert_*.py`: 팀원별 원본 리뷰 변환
- `scripts/insert_*.py`: SQLite 리뷰 적재
- `scripts/load_seed.py`: SQLite 시드 적용
- `scripts/save_rti_scores.py`: 로컬 RTI 계산·저장
- `scripts/create_rti_sample.py`: 백엔드 연동용 결과 샘플 생성
- `scripts/simulate_naver_worker_job.py`: Worker 처리 흐름 로컬 시뮬레이션
- `tests/`: API 계약과 주요 유틸·저장 조회 검사

## 데이터와 설정

- `db/`: MySQL 초기화 SQL, SQLite 스키마·시드, ERD
- `data/raw/`: 팀원별 원본 리뷰
- `data/normalized/`: 공통 형식으로 변환된 리뷰
- `data/debug/`: 크롤러 진단 산출물
- `output/`: RTI 결과와 백엔드 확인용 샘플
- `review_system.db`: 팀원이 함께 사용하는 로컬 SQLite 데이터베이스
- `api-spec/`: 백엔드 연동 API 명세
- `docs/`: 회의·설계·정책 초안과 결과 문서
- `.env.example`: 환경변수 예시
- `docker-compose.yml`: MySQL·Redis 인프라 실행 설정
- `.github/workflows/ci.yml`: Azure VM 배포 workflow

JSON·SQLite·이미지 파일은 형식상 주석을 지원하지 않으므로 파일 내부를
수정하지 않고 이 문서에서 역할을 설명한다. `artifacts/`는 현재 애플리케이션
코드와 무관한 별도 작업 산출물로 판단하여 이동하거나 수정하지 않는다.
