# Async Analysis Job/Queue Discussion

## 문서 목적

동환님이 제안한 비동기 분석 Job/Queue 구조에 대해 프론트, Spring 백엔드, FastAPI, Redis, DB가 함께 협의해야 할 항목을 정리한다.

이번 문서는 팀 협의 전 AI 파트 기준 회의 안건 정리를 목적으로 하며, 실제 코드 동작 변경은 포함하지 않는다.

## 1. 현재 제안된 전체 흐름

```txt
프론트 요청
-> Spring이 product_analysis_job 생성
-> Redis Queue에 분석 작업 등록
-> FastAPI Worker가 작업 수신
-> 크롤링 / RTI 분석 / 결과 저장
-> Job 상태 DONE 또는 FAILED 업데이트
-> 프론트가 SSE 또는 상태 조회로 완료 확인
```

협의 필요 사항:

- Spring이 Job 생성과 Queue 등록을 모두 담당할지
- FastAPI Worker가 Job 상태 변경까지 담당할지
- 프론트가 완료 여부를 SSE로 받을지, polling으로 조회할지
- DONE 이후 결과 조회 API가 기존 API를 재사용할지, 별도 API가 필요할지

## 2. Job 상태값 협의

현재 후보:

```txt
PENDING
RUNNING
DONE
FAILED
```

대안 후보:

```txt
PENDING
PROCESSING
SUCCESS
FAILED
```

협의 필요 사항:

- `RUNNING`과 `PROCESSING` 중 어떤 표현을 사용할지
- `DONE`과 `SUCCESS` 중 어떤 표현을 사용할지
- DB enum 또는 varchar 정책
- 실패 후 재시도 상태가 필요한지
- 취소 상태(`CANCELED`)가 MVP에 필요한지

## 3. Redis Queue 메시지 구조 협의

예상 메시지:

```json
{
  "jobId": "uuid",
  "mall": "NAVER",
  "productId": "7195971829",
  "productUrl": "https://smartstore.naver.com/main/products/7195971829",
  "platform": "NAVER"
}
```

협의 필요 사항:

- `mall`과 `platform`을 둘 다 유지할지, 하나로 통일할지
- `productId`를 프론트/Spring에서 추출할지, FastAPI Worker에서 URL 기반으로 추출할지
- message version 필드가 필요한지
- 재시도 횟수, 요청자, 생성 시각 같은 메타데이터를 포함할지
- Queue 이름과 dead letter queue 필요 여부

## 4. FastAPI Worker 책임 범위 협의

후보 책임 범위:

- Redis Queue consume
- Job 상태 업데이트
- 크롤링
- raw JSON 저장
- 리뷰 정규화
- reviews DB insert
- RTI 분석
- review_trust_scores 저장

협의 필요 사항:

- FastAPI Worker가 DB write까지 직접 담당할지
- Spring API를 통해 저장/상태 변경을 요청할지
- 크롤링, 정규화, RTI 분석을 하나의 Worker에서 처리할지
- 단계별 실패 지점을 Job 상태 또는 로그로 남길지
- Worker idempotency 기준을 어떻게 둘지

## 5. Job 상태 업데이트 방식 협의

후보 1: FastAPI가 DB 직접 update

- 장점: 구현 흐름이 단순하고 Worker가 상태를 즉시 반영할 수 있음
- 단점: FastAPI가 Spring 소유 DB 모델에 강하게 결합될 수 있음

후보 2: FastAPI가 Spring API 호출로 상태 update

- 장점: DB write 책임을 Spring 쪽으로 모을 수 있음
- 단점: 내부 API 계약, 인증, 장애 처리, 재시도 정책이 추가로 필요함

협의 필요 사항:

- product_analysis_job 테이블의 소유권
- FastAPI DB 접근 허용 범위
- Spring 내부 API가 필요한 경우 endpoint 계약
- 실패 시 상태 업데이트 보장 방식

## 6. Crawler MVP 범위 협의

MVP 후보:

- 상품 URL 1개 기준
- 리뷰 일부 수집
- raw JSON 저장
- 기존 v1 파이프라인 재사용

협의 필요 사항:

- 리뷰 수집 개수 기준
- 정렬 기준 또는 페이지 기준
- raw JSON 저장 위치와 스키마
- 크롤링 실패와 리뷰 0개 수집을 같은 실패로 볼지
- 기존 v1 파이프라인 재사용 범위

## 7. RTI 결과 저장 정책 협의

저장 대상:

- `review_trust_scores`

협의 필요 사항:

- `review_id` 기준 중복 처리 방식
- 기존 score가 있으면 재사용할지
- 기존 score가 있어도 재분석할 조건이 있는지
- RTI 모델 버전 또는 분석 기준 버전을 저장할지
- 일부 리뷰만 분석 성공한 경우 Job을 DONE으로 볼지 FAILED로 볼지

## 8. 실패 처리 기준 협의

실패 케이스 후보:

- 크롤링 실패
- 리뷰 0개 수집
- DB insert 실패
- RTI 분석 실패
- Job 상태 업데이트 실패

협의 필요 사항:

- `error_message` 저장 여부
- 사용자에게 노출할 에러 메시지와 내부 로그 메시지 분리 여부
- 재시도 가능한 실패와 불가능한 실패 구분
- 부분 성공 상태가 필요한지
- FAILED 상태에서 프론트가 어떤 안내를 보여줄지

## 9. 프론트 완료 조회 흐름 협의

예상 흐름:

- 분석 요청 후 `jobId` 반환
- 프론트가 SSE 또는 polling으로 상태 확인
- DONE 이후 결과 조회 API 호출
- FAILED인 경우 실패 UI 표시

협의 필요 사항:

- 최초 요청 응답에 포함할 필드
- SSE와 polling 중 MVP 방식
- polling 주기와 timeout
- DONE 이후 결과 조회 API 경로
- FAILED 처리 UI와 재시도 버튼 필요 여부

## 10. 기존 실시간 API 유지 여부

대상:

- 기존 FastAPI `product-detail`
- 기존 FastAPI `product-list`
- 기존 FastAPI `risk-report`

협의 필요 사항:

- 비동기 Job/Queue 구조 도입 후 기존 endpoint를 유지할지
- 개발/디버깅용으로 유지할지
- 프론트가 더 이상 직접 호출하지 않도록 할지
- 제거 또는 deprecated 처리 시점

## 11. Saved RTI Score API 연결 시점

현재 제안:

- Job/Queue/Worker 구조 확정 전까지 API 연결 보류
- 협의 후 `product-detail` 또는 결과 조회 API에서 saved RTI 사용 검토

협의 필요 사항:

- saved RTI score 조회 API를 기존 실시간 API에 붙일지
- 비동기 분석 완료 후 결과 조회 API에 붙일지
- 기존 score 재사용 정책과 연결할지
- 프론트 표시 기준을 어떤 API 응답에 맞출지

## 12. AI 파트에서 협의 전 보류할 개발

협의 전 보류 대상:

- `main.py` endpoint 변경
- Redis Worker 구현
- 크롤러 구현
- `product_analysis_job` 상태 업데이트 코드
- saved RTI API 연결

## 13. AI 파트에서 지금 할 수 있는 준비 작업

현재 가능한 준비 작업:

- 문서화
- 메시지 구조 후보 정리
- Worker 책임 범위 정리
- 크롤러 MVP 전략 정리
- 실패 처리 케이스 정리

## 회의에서 결정하면 좋은 항목

- Job 상태값 최종 명칭
- Redis Queue 메시지 최종 스키마
- FastAPI Worker의 DB 접근 허용 여부
- Job 상태 업데이트 주체
- Crawler MVP 수집 범위
- RTI 결과 중복 처리 정책
- 실패 상태와 에러 메시지 저장 정책
- 프론트 완료 확인 방식
- 기존 실시간 API 유지 범위
- saved RTI score API 연결 시점
