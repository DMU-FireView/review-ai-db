# Product Analysis Job Status Draft

## 문서 목적

비동기 분석 Job 구조에서 `product_analysis_job.status` 값은 Spring, FastAPI Worker, 프론트가 모두 함께 사용하는 공통 상태값이다.

따라서 구현 전에 상태값 이름과 의미를 팀에서 통일해야 한다.

## 1. 상태값이 필요한 이유

비동기 분석 구조에서는 요청 즉시 결과를 반환하지 않고, Job 상태를 통해 진행 상황을 추적한다.

예상 흐름:

```txt
PENDING
-> RUNNING
-> DONE
```

또는

```txt
PENDING
-> RUNNING
-> FAILED
```

상태값은 다음 영역에서 공통 기준으로 사용될 수 있다.

- Spring: Job 생성, 상태 조회 API, 상태 enum 관리
- FastAPI Worker: Queue consume 이후 작업 시작/완료/실패 상태 업데이트
- 프론트: 분석 진행 중 UI, 완료 후 결과 조회, 실패 안내 UI
- DB: Job 이력과 상태 추적

## 2. 현재 후보 상태값

현재 동환님이 추가한 schema comment 기준 상태값 후보:

```txt
PENDING
RUNNING
DONE
FAILED
```

각 상태의 의미:

- `PENDING`: Job 생성 완료, 아직 Worker가 처리하지 않음
- `RUNNING`: Worker가 작업을 가져가 크롤링/분석 중
- `DONE`: 크롤링/분석/저장이 정상 완료됨
- `FAILED`: 크롤링/분석/저장 중 실패함

## 3. 대안 상태값

팀에서 아래 대안도 검토할 수 있다.

```txt
PROCESSING 대신 RUNNING
SUCCESS 대신 DONE
```

비교 기준:

```txt
- 프론트에서 이해하기 쉬운지
- Spring 코드 enum과 맞는지
- FastAPI Worker 코드에서 쓰기 쉬운지
- DB 저장값으로 명확한지
```

검토 포인트:

- `RUNNING`은 Worker가 실제로 작업을 수행 중이라는 느낌이 강하다.
- `PROCESSING`은 사용자 UI나 일반적인 작업 상태 표현으로 자연스럽다.
- `DONE`은 작업 완료를 짧고 명확하게 표현한다.
- `SUCCESS`는 실패(`FAILED`)와 대비가 명확하지만, 완료된 결과가 부분 성공일 수 있는 경우 의미가 애매해질 수 있다.

## 4. 추천 상태값

AI 파트 기준 추천은 아래 4개이다.

```txt
PENDING
RUNNING
DONE
FAILED
```

이유:

```txt
- 단순함
- 동환님 schema comment와 일치
- Worker 처리 흐름과 직관적으로 맞음
- 초기 MVP에 충분함
```

초기 MVP에서는 상태값을 최소화하고, 재시도/부분 성공/취소 같은 확장 상태는 실제 필요가 확인된 뒤 추가하는 것이 좋다.

## 5. 상태 전이 규칙

가능한 상태 전이:

```txt
PENDING -> RUNNING
RUNNING -> DONE
RUNNING -> FAILED
FAILED -> PENDING 또는 RUNNING은 재시도 정책 확정 후 결정
```

허용하지 않는 전이 예시:

```txt
DONE -> RUNNING
DONE -> FAILED
PENDING -> DONE
```

단, 재분석/재시도 기능이 생기면 별도 정책이 필요하다.

검토 포인트:

- `PENDING -> DONE`을 허용하지 않으면 Worker가 반드시 `RUNNING` 상태를 기록해야 한다.
- `DONE` 이후 재분석 요청은 기존 Job을 되돌릴지, 새 Job을 생성할지 정해야 한다.
- `FAILED` 이후 재시도는 같은 Job을 사용할지, 새 Job을 생성할지 정해야 한다.

## 6. 실패 상태 처리

`FAILED` 상태가 되면 함께 기록하면 좋은 정보:

```txt
error_message
failed_at 또는 updated_at
retry_count
```

현재 schema에는 이 컬럼들이 없으므로, 실제 구현 전 협의가 필요하다.

협의할 내용:

- `error_message`를 DB에 저장할지
- 사용자 노출용 메시지와 내부 디버깅 메시지를 분리할지
- 실패 시각을 `updated_at`만으로 볼지, `failed_at`을 따로 둘지
- 재시도를 고려해 `retry_count`를 둘지

## 7. 리뷰 0개 수집 케이스

크롤링은 성공했지만 리뷰가 0개인 경우 상태를 어떻게 볼지 협의가 필요하다.

후보:

```txt
FAILED
DONE_WITH_NO_REVIEWS
DONE + review_count = 0
```

초기에는 상태값을 단순하게 유지하기 위해 `FAILED` 또는 `DONE + review_count = 0` 중 하나로 정할 필요가 있다.

검토 포인트:

- 리뷰 0개가 크롤링 실패인지, 정상적으로 리뷰가 없는 상품인지 구분 가능한지
- 프론트에서 "분석 실패"와 "리뷰 없음"을 다르게 보여줘야 하는지
- `DONE_WITH_NO_REVIEWS`를 추가하면 상태값은 명확해지지만 MVP 상태 관리가 복잡해질 수 있다.
- `DONE + review_count = 0`을 사용하려면 review count를 어디에 저장하거나 계산할지 정해야 한다.

## 8. 최종 협의 필요 항목

팀 협의가 필요한 항목:

```txt
- DONE vs SUCCESS
- RUNNING vs PROCESSING
- 리뷰 0개 수집 상태 처리
- FAILED 시 error_message 저장 여부
- 재시도 상태가 필요한지
- DB CHECK 제약을 둘지, 애플리케이션에서만 관리할지
```

AI 파트 기준으로는 초기 MVP에서 `PENDING`, `RUNNING`, `DONE`, `FAILED` 4개 상태를 사용하고, 리뷰 0개/재시도/부분 성공은 별도 정책이 필요해진 시점에 확장하는 방향을 우선 검토할 수 있다.
