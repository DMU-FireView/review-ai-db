# Redis 분석 작업 메시지 구조 초안

## 문서 목적

비동기 분석 구조에서 Spring은 분석 요청을 받은 뒤 Redis Queue에 작업 메시지를 등록하고, FastAPI Worker는 메시지를 꺼내 크롤링 및 RTI 분석을 수행한다.

Spring과 FastAPI가 동일한 형식으로 작업 정보를 해석할 수 있도록 Redis Queue 메시지 구조의 초안을 정의한다.

이 문서는 팀 협의를 위한 초안이며, 실제 Redis 연결이나 Worker 동작을 구현하지 않는다.

## 1. Redis 메시지가 필요한 이유

비동기 분석 구조에서는 Spring이 요청을 받은 즉시 분석을 완료하지 않고, 분석에 필요한 작업 정보를 Redis Queue에 등록한다. FastAPI Worker는 Queue에서 메시지를 가져와 크롤링과 분석을 수행한다.

```text
프론트 요청
→ Spring이 product_analysis_job 생성
→ Redis Queue에 메시지 push
→ FastAPI Worker가 메시지 consume
→ 크롤링/분석 수행
```

Queue 메시지는 Spring에서 생성된 작업과 FastAPI Worker가 수행할 분석을 연결하는 공통 계약 역할을 한다.

## 2. 추천 메시지 구조

아래 JSON 구조를 Redis Queue에 등록할 분석 작업 메시지의 초안으로 제안한다.

```json
{
  "jobId": "uuid",
  "mall": "NAVER",
  "productId": "7195971829",
  "productUrl": "https://smartstore.naver.com/main/products/7195971829",
  "requestedAt": "2026-06-09T12:00:00"
}
```

## 3. 필드 설명

| 필드 | 설명 |
| --- | --- |
| `jobId` | `product_analysis_job.job_id`와 연결되는 작업 ID |
| `mall` | 쇼핑몰 또는 플랫폼 구분값 |
| `productId` | 쇼핑몰에서 사용하는 상품 고유 번호 |
| `productUrl` | FastAPI Worker가 크롤링할 대상 URL |
| `requestedAt` | 분석 요청이 생성된 시각 |

## 4. 필수 필드 후보

AI 파트에서는 아래 필드를 필수값으로 제안한다.

```text
jobId
mall
productId
productUrl
```

`requestedAt`은 작업 처리 자체에 반드시 필요한 값은 아니므로 선택값으로 둘 수 있다.

## 5. product_analysis_job과의 관계

현재 `product_analysis_job`에는 아래 컬럼이 있다.

```text
job_id
mall
product_id
status
created_at
updated_at
```

Queue 메시지의 `jobId`, `mall`, `productId`는 각각 DB의 job row와 연결된다.

| Queue 메시지 | `product_analysis_job` |
| --- | --- |
| `jobId` | `job_id` |
| `mall` | `mall` |
| `productId` | `product_id` |

현재 테이블에는 `product_url` 컬럼이 없다. 따라서 `productUrl`을 Redis 메시지에만 포함할지, DB에도 저장할지는 별도 협의가 필요하다.

## 6. 메시지 검증 기준

FastAPI Worker는 메시지를 받은 뒤 최소한 아래 항목을 확인해야 한다.

```text
- jobId가 있는지
- mall이 있는지
- productId가 있는지
- productUrl이 있는지
- productUrl이 지원 가능한 플랫폼 URL인지
```

필수값의 빈 문자열 허용 여부, URL 검증 방식, 지원 플랫폼 목록 등 세부 기준은 구현 전에 추가로 합의한다.

## 7. 실패 처리

메시지 형식이 잘못된 경우 아래와 같은 처리를 예상한다.

```text
- jobId가 있으면 해당 job을 FAILED로 업데이트
- error_message에 메시지 파싱 실패 원인 기록
- jobId가 없으면 로그만 남기고 처리 중단
```

위 내용은 예상 처리 방안이며, 상태 변경 주체와 오류 저장 방식 등 실제 구현은 팀 협의 후 진행한다.

## 8. 협의 필요 항목

아래 항목은 Spring과 FastAPI 간 협의가 필요하다.

```text
- productUrl을 Queue 메시지에만 둘지 DB에도 저장할지
- mall과 platform 중 필드명을 무엇으로 통일할지
- requestedAt이 필요한지
- retryCount를 메시지에 포함할지
- Redis Queue 이름을 무엇으로 할지
```

## 9. 주의사항

- 이 문서는 Redis 분석 작업 메시지 구조에 대한 초안이다.
- 실제 Redis 연결 코드는 구현하지 않는다.
- Spring API endpoint, DB schema, Redis/Worker 코드 및 크롤러 코드의 변경을 포함하지 않는다.
