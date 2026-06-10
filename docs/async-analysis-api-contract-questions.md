# 비동기 분석 API 계약 질문

## 1. 문서 목적

비동기 분석 Job/Queue 구조에서는 프론트엔드, Spring Backend, FastAPI가 동일한 API 흐름과 역할 분담을 이해해야 한다.

특히 다음 항목은 실제 구현 전에 팀 합의가 필요하다.

- 분석 요청 API를 누가 담당할지
- `jobId`를 누가 생성하고 반환할지
- 상태 조회 API를 누가 제공할지
- 결과 조회 API를 누가 제공할지
- SSE 또는 polling을 어떤 방식으로 사용할지
- FastAPI가 직접 프론트에 응답할지, Spring을 통해 응답할지

이 문서는 구현 전에 팀이 확인해야 할 API 계약 질문을 정리한 협의용 초안이다. 아래 endpoint와 응답 payload 예시는 확정된 API 계약이 아니다.

## 2. 전체 API 흐름 후보

```text
Frontend
→ Spring Backend: 분석 요청
→ Spring Backend: product_analysis_job 생성
→ Spring Backend: Redis Queue 메시지 등록
→ Frontend: jobId 반환
→ FastAPI Worker: Queue 작업 처리
→ FastAPI Worker: RTI 분석 결과 저장
→ Frontend: 상태 조회 또는 SSE 수신
→ Frontend: 결과 조회
```

이 흐름에서는 Spring Backend가 프론트용 API와 Job 생성 및 Queue 등록을 담당하고, FastAPI Worker가 크롤링과 RTI 분석 등 내부 작업을 담당하는 구조를 가정한다.

실제 구현 전에는 Job 생성과 Queue 등록 사이의 실패 처리, 상태 업데이트 주체, 결과 조회 경로를 함께 확정해야 한다.

## 3. 분석 요청 API 질문

### 협의 질문

- [ ] 프론트는 분석 요청을 Spring Backend로 보낼지 FastAPI로 보낼지
- [ ] 요청 body에는 `productId`만 보낼지 `productUrl`까지 보낼지
- [ ] `mall` 또는 `platform` 값을 프론트가 보낼지 Spring Backend가 URL 등을 기준으로 판단할지
- [ ] 같은 상품에 대한 중복 요청이 들어오면 새 Job을 만들지 기존 진행 중인 Job을 재사용할지
- [ ] 이미 완료된 saved RTI가 있으면 새 Job을 만들지 기존 결과를 반환할지
- [ ] 요청 직후 응답은 `jobId`만 제공할지 `status`와 사용자 메시지도 함께 제공할지
- [ ] 요청 API의 HTTP status code를 `200 OK`, `201 Created`, `202 Accepted` 중 무엇으로 할지
- [ ] Job 생성 성공 후 Redis Queue 등록이 실패하면 요청을 실패 처리할지 Job을 `FAILED`로 변경할지
- [ ] 인증 사용자와 Job 소유 관계를 저장하고 조회 시 검증할지

### 예상 응답 초안

```json
{
  "jobId": "uuid",
  "status": "PENDING",
  "message": "분석 요청이 등록되었습니다."
}
```

`jobId` 형식, status 값, message 제공 여부 및 HTTP status code는 팀 협의 후 확정해야 한다.

## 4. Job 상태 조회 API 질문

### 협의 질문

- [ ] 상태 조회 API는 Spring Backend가 제공할지 FastAPI가 제공할지
- [ ] 조회 기준은 `jobId`인지 `productId`인지
- [ ] `productId`로 조회할 경우 여러 Job 중 어떤 Job을 반환할지
- [ ] 응답에 `status`만 제공할지 `progress`와 `message`도 제공할지
- [ ] `progress`를 제공한다면 백분율인지 현재 처리 단계인지
- [ ] `FAILED`일 때 사용자 메시지와 내부 `error_message`를 분리할지
- [ ] 존재하지 않거나 접근 권한이 없는 Job의 응답 형식을 어떻게 할지
- [ ] polling 부하를 줄이기 위한 cache 또는 호출 제한이 필요한지
- [ ] `PENDING`, `RUNNING`, `DONE`, `FAILED` 외 상태가 필요한지

### 예상 응답 초안

```json
{
  "jobId": "uuid",
  "status": "RUNNING",
  "message": "리뷰를 분석 중입니다."
}
```

내부 오류 정보는 상태 조회 응답에 직접 포함하지 않고, 사용자용 `message`와 분리하는 방향을 검토할 수 있다.

## 5. 결과 조회 API 질문

### 협의 질문

- [ ] 결과 조회 API는 Spring Backend가 제공할지 FastAPI가 제공할지
- [ ] 결과 조회 기준은 `jobId`인지 `productId`인지
- [ ] `DONE` 상태 전에는 빈 결과를 반환할지, 현재 대기 상태를 반환할지, 별도 오류로 응답할지
- [ ] 조회 시 DB에 저장된 saved RTI를 사용해 응답할지
- [ ] 기존 `product-detail`, `product-list`, `risk-report` API를 재사용할지
- [ ] 비동기 분석 전용 결과 조회 API를 새로 만들지
- [ ] 결과 응답에 Job 상태를 함께 포함할지
- [ ] 리뷰 상세 목록을 한 번에 반환할지 pagination을 적용할지
- [ ] 분석 결과가 일부만 저장된 경우 응답을 허용할지
- [ ] 재분석된 결과의 버전 또는 최신 결과 판별 기준이 필요한지

### 예상 응답 초안

```json
{
  "jobId": "uuid",
  "status": "DONE",
  "productId": "7195971829",
  "summary": {
    "averageRti": 82,
    "reviewCount": 120,
    "riskLevel": "safe"
  },
  "reviews": []
}
```

`summary`와 `reviews`의 필드명 및 자료형은 기존 API 응답 구조와의 호환성을 확인한 뒤 확정해야 한다.

## 6. SSE 또는 Polling 질문

### 협의 질문

- [ ] 프론트 완료 알림은 SSE로 받을지 polling으로 조회할지
- [ ] 초기 MVP와 이후 운영 구조에서 같은 방식을 사용할지
- [ ] SSE는 Spring Backend가 담당할지 FastAPI가 담당할지
- [ ] Spring Backend가 SSE를 담당한다면 DB 상태를 감지하는 방식을 어떻게 할지
- [ ] polling 주기는 몇 초로 할지
- [ ] polling의 최대 횟수 또는 최대 대기 시간을 둘지
- [ ] `DONE` 및 `FAILED` 이벤트 payload에 어떤 필드를 포함할지
- [ ] SSE 연결이 끊어진 경우 자동 재연결 또는 polling fallback을 제공할지
- [ ] 페이지 새로고침 후 기존 Job 구독을 복구할지
- [ ] 한 사용자가 여러 Job을 동시에 구독할 수 있는지

### SSE 이벤트 예시

```json
{
  "jobId": "uuid",
  "status": "DONE",
  "message": "분석이 완료되었습니다."
}
```

SSE 이벤트는 완료 사실만 전달하고 상세 결과는 별도 결과 조회 API로 가져오는 방식도 검토할 수 있다.

## 7. FastAPI와 Spring 책임 분리 질문

### 협의 질문

- [ ] FastAPI가 프론트용 API를 직접 제공할지
- [ ] Spring Backend가 프론트용 API를 제공하고 FastAPI는 내부 분석만 담당할지
- [ ] FastAPI가 `product_analysis_job`, `reviews`, `review_trust_scores` 등 DB를 직접 수정해도 되는지
- [ ] FastAPI가 Spring 내부 API를 호출해 Job 상태를 업데이트해야 하는지
- [ ] FastAPI와 Spring Backend가 같은 테이블을 수정할 경우 책임 컬럼과 transaction 경계를 어떻게 나눌지
- [ ] 내부 API 호출 실패 시 재시도와 인증 방식을 어떻게 할지
- [ ] 프론트가 두 백엔드의 인증, 주소 및 오류 형식을 각각 알아야 하는 구조를 허용할지
- [ ] API 응답 DTO와 내부 Worker 메시지 DTO를 분리할지

### 초기 추천 방향

초기 구조에서는 Frontend가 Spring Backend와 통신하고, FastAPI는 내부 Worker 및 AI 분석 역할에 집중하는 방식이 책임 분리와 프론트 API 일관성 측면에서 유리할 수 있다.

다만 DB 접근 권한, 상태 갱신 방식, 내부 API 운영 비용 및 기존 시스템 구조를 함께 검토해야 하며, 실제 결정은 팀 협의가 필요하다.

## 8. Saved RTI API 연결 질문

### 협의 질문

- [ ] saved RTI는 어떤 API에서 조회할지
- [ ] saved RTI 조회는 Spring Backend가 DB에서 직접 수행할지 FastAPI에 요청할지
- [ ] saved RTI가 없을 때 실시간 분석 fallback을 수행할지
- [ ] saved RTI가 없을 때 새 Job을 생성할지
- [ ] 새 Job을 생성한다면 결과 조회 요청이 Job 생성까지 담당해도 되는지
- [ ] `review_trust_scores` 조회 조건은 `review_id`인지 `product_id`인지
- [ ] 상품 결과 조회 시 리뷰별 score를 어떤 방식으로 묶을지
- [ ] 기존 API 응답 구조와 saved RTI 응답 구조를 맞출지
- [ ] 저장된 분석 결과의 유효 기간 또는 재분석 기준이 필요한지
- [ ] 여러 분석 버전 중 어떤 saved RTI를 반환할지

saved RTI가 없는 경우의 응답은 빈 결과, 분석 요청 안내, 자동 Job 생성 중 하나로 명확히 정해야 한다. 조회 API가 예상하지 못한 쓰기 작업을 수행하지 않도록 Job 생성 책임도 별도로 협의할 필요가 있다.

## 9. 실패 응답 질문

### 협의 질문

- [ ] `FAILED` 상태일 때 프론트 응답 형식을 어떻게 할지
- [ ] 내부 `error_message`를 프론트에 그대로 보여줄지
- [ ] 사용자용 `message`를 별도로 둘지
- [ ] 오류 유형 구분을 위한 사용자용 `errorCode`가 필요한지
- [ ] 재시도 버튼을 제공할지
- [ ] 재시도 시 기존 Job을 재사용할지 새 Job을 생성할지
- [ ] 재시도 가능한 실패와 불가능한 실패를 프론트가 구분해야 하는지
- [ ] HTTP 요청 자체의 실패와 비동기 Job 실패를 어떤 방식으로 구분할지

### 예상 응답 초안

```json
{
  "jobId": "uuid",
  "status": "FAILED",
  "message": "분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
}
```

DB 오류, stack trace, 내부 서비스 정보 등은 사용자 응답에서 제외하고 내부 `error_message` 또는 로그에 기록하는 방향을 검토해야 한다.

## 10. 기존 API 유지 여부 질문

### 협의 질문

- [ ] 기존 실시간 분석 API를 유지할지
- [ ] 기존 API를 개발 및 디버깅 용도로만 유지할지
- [ ] 비동기 구조가 완성되면 기존 API를 deprecated 처리할지
- [ ] deprecated 처리 시 종료 일정과 migration 안내가 필요한지
- [ ] 기존 응답 구조와 새 비동기 결과 응답 구조를 어떻게 맞출지
- [ ] 기존 API와 비동기 API가 동일한 분석 로직을 공유할지
- [ ] 두 방식이 동시에 동작할 때 중복 분석 및 중복 저장을 어떻게 방지할지
- [ ] API version을 분리해야 하는지

기존 API 유지 여부는 현재 사용처와 호환성 요구사항을 확인한 뒤 결정해야 한다.

## 11. 최종 협의 체크리스트

- [ ] 분석 요청 API 담당 주체
- [ ] 상태 조회 API 담당 주체
- [ ] 결과 조회 API 담당 주체
- [ ] `jobId` 생성 주체와 형식
- [ ] `productUrl` 전달 및 검증 방식
- [ ] `mall` / `platform` 판별 주체
- [ ] 중복 분석 요청 처리 방식
- [ ] SSE 또는 polling 선택
- [ ] polling 주기 또는 SSE 재연결 정책
- [ ] saved RTI 조회 위치
- [ ] saved RTI가 없을 때 fallback 정책
- [ ] FastAPI와 Spring Backend의 DB 및 상태 갱신 책임
- [ ] 실패 응답 형식과 사용자 메시지
- [ ] 기존 실시간 분석 API 유지 여부
- [ ] API 및 이벤트 payload의 필드명과 자료형
- [ ] 정상, 진행 중, 실패 응답의 HTTP status code

## 12. 결론

비동기 분석 구조에서는 API 계약이 확정되지 않은 상태에서 endpoint를 먼저 수정하면 Frontend, Spring Backend, FastAPI 사이에 요청 경로, 상태 해석 및 응답 구조 차이로 인한 연동 오류가 발생할 수 있다.

따라서 실제 `main.py` endpoint 수정이나 saved RTI API 연결 전에 이 문서의 질문을 기준으로 담당 주체, 요청 및 응답 payload, 완료 조회 방식, 실패 처리, 기존 API 호환성을 먼저 협의하는 것이 안전하다.

이 문서는 협의를 위한 초안이며 코드, API endpoint, DB schema, Redis/Worker 및 크롤러 구현을 변경하지 않는다.
