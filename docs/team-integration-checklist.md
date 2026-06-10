# 비동기 분석 구조 팀 연동 체크리스트

## 1. 문서 목적

비동기 분석 Job/Queue 구조는 프론트엔드, Spring 백엔드, FastAPI, Redis, DB가 함께 연결되는 구조이다.

이 문서는 실제 구현 전에 각 파트가 전체 흐름을 동일하게 이해하고, 역할과 책임 범위 및 파트 간 계약을 명확히 하기 위한 협의용 체크리스트이다.

현재 코드 동작, API endpoint, DB schema, Redis/Worker 및 크롤러 구현 변경은 포함하지 않는다.

## 2. 전체 연동 흐름

```text
Frontend
→ Spring Backend
→ product_analysis_job
→ Redis Queue
→ FastAPI Worker
→ Crawler
→ RTI Analysis
→ review_trust_scores
→ Result Query / SSE / Polling
→ Frontend Render
```

단계별 책임 주체, 입력 및 출력 데이터, 실패 처리 방식이 확정되어야 각 파트가 독립적으로 구현하고 연동 테스트를 진행할 수 있다.

## 3. Frontend 체크리스트

- [ ] 분석 요청 버튼 또는 자동 분석 트리거가 필요한지 확정
- [ ] 중복 요청 방지를 위한 버튼 비활성화 또는 요청 상태 표시 방식 확정
- [ ] 요청 후 즉시 결과 화면으로 이동할지, 별도 대기 화면을 보여줄지 확정
- [ ] Spring Backend가 반환한 `jobId`를 저장해야 하는지 확정
- [ ] `jobId` 저장 범위 확정: 메모리, 상태 관리 도구, URL 또는 브라우저 저장소
- [ ] 완료 상태 확인에 SSE를 사용할지 polling을 사용할지 확정
- [ ] polling 사용 시 호출 주기와 최대 대기 시간 확정
- [ ] 페이지 새로고침 또는 재접속 시 진행 중인 Job을 복구할지 확정
- [ ] `DONE` 상태일 때 결과 조회 API와 렌더링 방식 확정
- [ ] `FAILED` 상태일 때 사용자에게 보여줄 메시지와 재요청 동작 확정
- [ ] 리뷰 0개 수집 상태를 어떻게 표시할지 확정
- [ ] 내부 오류 메시지를 프론트에 직접 노출하지 않는 방식 확정

## 4. Spring Backend 체크리스트

- [ ] 분석 요청 API를 Spring Backend가 담당할지 확정
- [ ] 분석 요청 시 `product_analysis_job` row를 생성할지 확정
- [ ] Job 생성 시 초기 `status` 값 확정
- [ ] Redis Queue에 메시지를 push할지 확정
- [ ] DB Job 생성과 Queue push 사이의 정합성 보장 방식 확정
- [ ] 생성한 `jobId`를 프론트에 반환할지 확정
- [ ] Job 상태 조회 API를 제공할지 확정
- [ ] 분석 결과 조회 API의 책임 범위 확정
- [ ] SSE 연결과 상태 알림을 Spring Backend가 담당할지 확정
- [ ] FastAPI가 `product_analysis_job`을 직접 update하는 것을 허용할지 확정
- [ ] FastAPI가 Spring API를 통해 상태를 update해야 하는지 확정
- [ ] Queue push 실패 시 Job 상태와 응답 처리 방식 확정
- [ ] 동일 상품에 대한 중복 분석 요청 처리 정책 확정

## 5. FastAPI 체크리스트

- [ ] Redis Queue consume을 FastAPI Worker가 담당할지 확정
- [ ] FastAPI API 프로세스와 Worker 프로세스를 분리할지 확정
- [ ] Queue 메시지 형식과 필수 필드 검증을 담당할지 확정
- [ ] 유효하지 않은 메시지의 로그 및 실패 처리 방식 확정
- [ ] 크롤링 실행을 담당할지 확정
- [ ] 크롤링 raw JSON 저장을 담당할지 확정
- [ ] raw JSON 저장 위치와 파일명 또는 식별 기준 확정
- [ ] raw JSON을 normalized review로 변환하는 작업을 담당할지 확정
- [ ] `reviews` DB insert를 담당할지 확정
- [ ] RTI 분석을 담당할지 확정
- [ ] `review_trust_scores` 저장을 담당할지 확정
- [ ] `product_analysis_job` 상태 업데이트를 담당할지 확정
- [ ] 단계별 성공 및 실패 로그 형식 확정
- [ ] 중복 메시지 소비 시 idempotency 보장 방식 확정
- [ ] 처리 중 프로세스 종료 시 Job 복구 방식 확정

## 6. DB 체크리스트

- [ ] `product_analysis_job` 컬럼과 각 컬럼의 책임 확정
- [ ] Job status 값과 상태 전이 규칙 확정
- [ ] `product_url` 저장 여부 확정
- [ ] 실패 원인 확인을 위한 `error_message` 저장 여부 확정
- [ ] 재시도 횟수 확인을 위한 `retry_count` 저장 여부 확정
- [ ] 작업 시작 및 종료 시각을 위한 `started_at` / `finished_at` 저장 여부 확정
- [ ] `created_at` / `updated_at` 갱신 주체와 기준 확정
- [ ] `reviews.review_date` 컬럼 존재 여부와 자료형 확인
- [ ] `reviews`의 중복 방지 key 또는 unique constraint 확인
- [ ] `review_trust_scores` 저장 형식과 필수 컬럼 확정
- [ ] 리뷰와 RTI 분석 결과의 참조 관계 확정
- [ ] 부분 저장 실패 시 transaction 및 rollback 범위 확정
- [ ] 현재 schema에 없는 컬럼의 추가 여부와 migration 시점 확정

## 7. Redis 체크리스트

- [ ] Redis Queue 이름과 환경별 naming 규칙 확정
- [ ] 메시지 JSON 구조 확정
- [ ] `jobId`, `productUrl`, mall/platform 등 필수 필드 확정
- [ ] 필드명과 데이터 타입 확정
- [ ] 메시지 schema version 필드가 필요한지 확정
- [ ] producer와 consumer의 직렬화 및 인코딩 방식 확정
- [ ] 유효하지 않은 메시지 처리 방식 확정
- [ ] 처리 실패 메시지를 재등록할지 별도 Queue로 이동할지 확정
- [ ] 재시도 대상, 횟수 및 간격 확정
- [ ] Dead Letter Queue가 필요한지 확정
- [ ] 메시지 처리 완료 확인과 ack 방식 확정
- [ ] 중복 전달 가능성을 고려한 처리 정책 확정
- [ ] Queue 적체 모니터링 기준 확정

## 8. Crawler 체크리스트

- [ ] v1에서 지원할 대상 플랫폼 확정
- [ ] `productUrl` 입력 및 검증 방식 확정
- [ ] URL에서 mall/platform과 상품 식별자를 추출하는 기준 확정
- [ ] 크롤링 raw JSON schema 확정
- [ ] raw JSON 필수 필드와 nullable 필드 확정
- [ ] 리뷰 최소 수집 개수 또는 최대 수집 개수 확정
- [ ] 페이지네이션 및 수집 종료 조건 확정
- [ ] 리뷰 0개 수집 시 실패 또는 정상 완료 처리 방식 확정
- [ ] 실제 리뷰 없음과 크롤링 실패를 구분할 수 있는지 확인
- [ ] 요청 타임아웃과 크롤링 최대 수행 시간 확정
- [ ] 크롤러 실패 시 재시도 또는 다른 수집 방식의 fallback 전략 확정
- [ ] 플랫폼 페이지 구조 변경 감지 및 알림 방식 확정
- [ ] 크롤링 정책, 요청 간격 및 접근 제한 검토

## 9. RTI / AI 체크리스트

- [ ] raw JSON을 normalized review로 변환하는 기준 확정
- [ ] 필수 입력 필드가 없거나 형식이 잘못된 리뷰의 처리 방식 확정
- [ ] `review_id` 생성 또는 매핑 기준 확정
- [ ] `review_id` 기준 중복 처리 정책 확정
- [ ] RTI 분석 대상 리뷰 선정 기준 확정
- [ ] RTI 분석 입력 및 출력 schema 확정
- [ ] RTI 분석 결과 저장 시점 확정
- [ ] 일부 리뷰의 RTI 분석만 실패한 경우 전체 Job 처리 방식 확정
- [ ] `review_trust_scores` 재분석 및 덮어쓰기 정책 확정
- [ ] saved RTI 조회 시점 확정
- [ ] saved RTI가 없을 때 실시간 분석, 재요청 또는 오류 응답 등 fallback 정책 확정
- [ ] 분석 모델 또는 로직 버전 저장 여부 확정
- [ ] 분석 결과의 재현 및 디버깅에 필요한 정보 확정

## 10. 파트 간 계약 확인

- [ ] Frontend와 Spring Backend 사이의 분석 요청 및 상태 조회 API 계약 확정
- [ ] Spring Backend와 Redis 사이의 메시지 생성 계약 확정
- [ ] Redis와 FastAPI Worker 사이의 메시지 소비 계약 확정
- [ ] FastAPI Worker와 Crawler 사이의 입력 및 출력 계약 확정
- [ ] Crawler raw JSON과 converter 사이의 schema 계약 확정
- [ ] normalized review와 RTI 분석 사이의 입력 계약 확정
- [ ] Spring Backend와 FastAPI 사이의 Job 상태 변경 책임 확정
- [ ] DB 저장 실패 또는 부분 성공 시 각 파트의 책임 확정
- [ ] 내부 오류 코드와 프론트 사용자 메시지의 매핑 기준 확정

## 11. 구현 전 최종 확인 항목

- [ ] 실제 구현 전에 API 계약 문서 확정
- [ ] Job status 값과 상태 전이 규칙 확정
- [ ] Redis message format 확정
- [ ] DB schema 변경 여부 확정
- [ ] Worker 책임 범위 확정
- [ ] 프론트 완료 조회 방식을 SSE 또는 polling 중에서 확정
- [ ] 실패 처리 및 재시도 정책 확정
- [ ] 리뷰 0개 수집 처리 방식 확정
- [ ] 파트별 담당자와 연동 테스트 일정 확정
- [ ] 정상, 실패, 재시도 시나리오의 통합 테스트 기준 확정

## 12. 결론

이 체크리스트는 실제 구현 전에 각 파트가 같은 비동기 분석 흐름을 이해하고, 역할과 책임 범위를 명확히 하기 위한 문서이다.

API 계약, Job 상태, Redis 메시지, DB 저장 구조, Worker 책임, 프론트 완료 조회 방식을 먼저 합의하면 구현 중 중복 작업과 파트 간 해석 차이를 줄일 수 있다.

이 문서는 협의를 위한 초안이며 코드, API endpoint, DB schema, Redis/Worker 및 크롤러 구현을 변경하지 않는다.
