# Product Analysis Job Schema Review

## 문서 목적

`product_analysis_job` 테이블은 비동기 분석 Job 상태를 추적하기 위한 테이블이다.

현재 main에 추가된 테이블을 실제 Redis Queue / FastAPI Worker / 크롤러 / 프론트 상태 조회 흐름에 연결하기 전에, AI 파트 기준으로 팀에서 협의해야 할 스키마 항목을 정리한다.

검토 대상 테이블:

```sql
CREATE TABLE product_analysis_job (
    job_id VARCHAR(36) PRIMARY KEY COMMENT '작업 고유 ID (UUID 사용 권장)',
    mall VARCHAR(50) NOT NULL COMMENT '쇼핑몰 구분 (예: NAVER, OLIVEYOUNG)',
    product_id VARCHAR(100) NOT NULL COMMENT '해당 쇼핑몰의 상품 고유 번호',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '진행 상태 (PENDING, RUNNING, DONE, FAILED)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '작업 요청 시간',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '상태 마지막 갱신 시간',

    INDEX idx_mall_product (mall, product_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 리뷰 분석 비동기 작업 관리 테이블';
```

## 1. 현재 테이블 역할

`product_analysis_job`은 상품 분석 요청을 비동기 Job으로 관리하기 위한 상태 추적 테이블이다.

예상 흐름:

```txt
Spring이 Job 생성
-> status = PENDING

FastAPI Worker가 작업 시작
-> status = RUNNING

분석 완료
-> status = DONE

실패
-> status = FAILED
```

이 테이블은 프론트가 분석 요청 이후 Job 진행 상태를 확인하고, Spring / FastAPI / Worker가 같은 작업 단위를 공유하기 위한 기준점 역할을 한다.

## 2. 현재 컬럼 정리

현재 컬럼:

```txt
job_id
mall
product_id
status
created_at
updated_at
```

컬럼 의미:

- `job_id`: 비동기 분석 작업의 고유 ID. UUID 사용이 권장되며, 프론트 상태 조회와 Worker 처리 단위의 기준이 된다.
- `mall`: 쇼핑몰 구분 값. 예를 들어 `NAVER`, `OLIVEYOUNG` 같은 플랫폼 또는 몰 식별자로 사용할 수 있다.
- `product_id`: 해당 쇼핑몰에서 사용하는 상품 고유 번호. `mall`과 함께 특정 상품을 식별한다.
- `status`: Job 진행 상태. 현재 기본값은 `PENDING`이며, 후보 상태는 `PENDING`, `RUNNING`, `DONE`, `FAILED`이다.
- `created_at`: 작업 요청이 생성된 시간. 분석 요청 접수 시점을 확인하는 데 사용된다.
- `updated_at`: Job 상태가 마지막으로 갱신된 시간. 상태 변경 시점을 추적하는 데 사용된다.

## 3. 현재 인덱스 정리

현재 인덱스:

```txt
idx_mall_product (mall, product_id)
idx_status (status)
```

인덱스 의미:

- `idx_mall_product (mall, product_id)`: 특정 쇼핑몰의 특정 상품에 대한 분석 Job을 조회할 때 도움이 된다. 예를 들어 동일 상품의 최근 분석 Job 확인, 중복 Job 생성 방지, 상품별 분석 이력 조회에 사용할 수 있다.
- `idx_status (status)`: 상태별 Job 조회에 도움이 된다. 예를 들어 `PENDING` 작업 목록 조회, `RUNNING` 작업 모니터링, `FAILED` 작업 확인에 사용할 수 있다.

## 4. 협의 필요 항목: product_url 저장 여부

현재 테이블에는 `product_url` 컬럼이 없다.

하지만 크롤링 작업에서는 `productUrl`이 중요하다.

협의할 내용:

```txt
- product_url을 product_analysis_job 테이블에도 저장할지
- 아니면 Redis Queue 메시지에만 포함할지
- DB에 저장하지 않을 경우 job 이력 추적에 문제가 없는지
```

AI 파트 의견:

```txt
크롤링 대상 URL은 작업 이력 추적에 중요하므로 product_url 컬럼을 두는 것을 검토할 필요가 있음
```

검토 포인트:

- Queue 메시지가 유실되거나 재처리가 필요한 경우 DB만으로 크롤링 대상을 복원할 수 있는지
- 같은 `mall`, `product_id`라도 실제 요청 URL이 다를 수 있는지
- 프론트 또는 Spring에서 전달한 원본 URL을 감사/디버깅 목적으로 보관할 필요가 있는지

## 5. 협의 필요 항목: error_message 저장 여부

현재 `FAILED` 상태가 있지만, 실패 원인을 저장할 컬럼은 없다.

협의할 내용:

```txt
- error_message 컬럼이 필요한지
- 크롤링 실패, DB insert 실패, 분석 실패 원인을 어떻게 남길지
```

AI 파트 의견:

```txt
FAILED 상태만으로는 원인 파악이 어렵기 때문에 error_message 컬럼이 있으면 디버깅에 도움이 됨
```

검토 포인트:

- 사용자에게 노출할 메시지와 내부 디버깅 메시지를 분리할지
- `error_message`에는 짧은 요약만 저장하고 상세 로그는 별도 로그 시스템에 남길지
- 실패 원인을 코드화하기 위해 `error_code` 같은 별도 컬럼도 필요한지

## 6. 협의 필요 항목: started_at / finished_at 필요 여부

현재는 `created_at`, `updated_at`만 있다.

협의할 내용:

```txt
- 작업 시작 시간을 started_at으로 따로 저장할지
- 작업 종료 시간을 finished_at으로 따로 저장할지
- 분석 소요 시간을 계산할 필요가 있는지
```

AI 파트 의견:

```txt
Worker 처리 시간과 병목 확인을 위해 started_at / finished_at 컬럼을 검토할 수 있음
```

검토 포인트:

- `created_at`과 `started_at`의 차이를 통해 Queue 대기 시간을 계산할 수 있는지
- `started_at`과 `finished_at`의 차이를 통해 실제 Worker 처리 시간을 계산할 수 있는지
- 크롤링, DB 저장, RTI 분석 단계별 시간이 필요한지

## 7. 협의 필요 항목: retry_count 필요 여부

크롤링/Queue 작업은 실패 가능성이 있다.

협의할 내용:

```txt
- 실패 시 재시도할지
- 재시도 횟수를 retry_count로 저장할지
- 몇 회까지 재시도할지
```

검토 포인트:

- 크롤링 실패처럼 재시도 가치가 있는 실패와, 요청 데이터 오류처럼 재시도해도 해결되지 않는 실패를 구분할지
- Redis Queue 재시도 정책과 DB의 `retry_count`를 어떻게 동기화할지
- 최대 재시도 횟수 초과 시 최종 상태를 `FAILED`로 둘지 별도 상태를 둘지

## 8. 협의 필요 항목: status 값 제한

현재 `status`는 `VARCHAR(20)`이다.

협의할 내용:

```txt
- PENDING / RUNNING / DONE / FAILED 값으로 통일할지
- DB 레벨에서 CHECK 제약을 둘지
- 애플리케이션 레벨에서만 관리할지
```

검토 포인트:

- `DONE`과 `SUCCESS`, `RUNNING`과 `PROCESSING` 중 어떤 표현으로 통일할지
- Spring, FastAPI, 프론트에서 같은 상태 문자열을 공유할지
- DB CHECK 제약을 둘 경우 배포/마이그레이션 환경에서 문제가 없는지
- 향후 `CANCELED`, `RETRYING`, `PARTIAL_FAILED` 같은 상태가 필요할 가능성이 있는지

## 9. 확인 필요 항목: reviews.review_date

현재 `schema.sql`의 `reviews` 테이블에 `review_date`가 보이지 않을 수 있다.

하지만 `main.py`에서는 `review_date`를 사용한다.

확인할 내용:

```txt
- reviews 테이블에 review_date 컬럼이 실제 운영 DB에 있는지
- schema.sql에도 review_date를 반영해야 하는지
- trend 계산과 date 응답에 필요한 필드인지
```

중요:

- 이 문서에서는 schema를 수정하지 않는다.
- `reviews.review_date`는 확인 필요 항목으로만 기록한다.
- 실제 반영 여부는 팀 협의 후 별도 스키마 변경 작업으로 다룬다.

## 10. 결론

`product_analysis_job` 테이블은 비동기 분석 구조의 출발점으로 적절하다.

다만 실제 Redis Queue / FastAPI Worker / 크롤러 / 프론트 상태 조회 흐름에 연결하기 전 아래 항목은 팀 협의가 필요하다.

```txt
- product_url 저장 여부
- error_message 저장 여부
- started_at / finished_at 필요 여부
- retry_count 필요 여부
- status 값 표준화
- reviews.review_date schema 반영 여부
```

AI 파트에서는 협의 전까지 실제 코드 동작 변경 없이, Queue 메시지 구조와 Worker 책임 범위, 실패 처리 정책을 문서 기준으로 먼저 정리하는 것이 안전하다.
