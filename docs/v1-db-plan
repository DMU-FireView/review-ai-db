# Re:view AI Server v1 DB Plan

## 1. 목적

v1에서는 v0의 테스트용 DB 구조를 실제 리뷰 데이터 누적이 가능한 구조로 개선한다.

v0에서는 Swagger 테스트와 데모를 위해 서버 실행 시 seed 데이터를 기반으로 DB를 재생성하는 방식이 사용되었다.  
v1에서는 실제 리뷰 데이터가 지속적으로 쌓일 수 있도록 DB 초기화 방식, 데이터 insert 방식, 중복 방지 기준, RTI 결과 저장 방식을 정리한다.

---

## 2. 현재 v0 DB 구조

v0 기준 DB는 SQLite 기반 테스트 DB로 구성되어 있다.

주요 테이블은 아래와 같다.

| 테이블명 | 역할 |
|---|---|
| `products` | 상품 정보 저장 |
| `reviews` | 리뷰 원문 및 메타데이터 저장 |
| `review_trust_scores` | RTI 분석 결과 저장용 테이블 |

현재 v0는 테스트 편의를 위해 서버 실행 시 테이블을 DROP 후 다시 생성할 수 있다.

```txt
서버 실행
→ 기존 테이블 DROP
→ products / reviews / review_trust_scores 재생성
→ seed 데이터 삽입
```

이 구조는 Swagger 테스트에는 적합하지만, 실제 데이터가 누적되어야 하는 v1 구조에는 적합하지 않다.

---

## 3. v0 DB 구조의 한계

현재 v0 DB 구조의 한계는 아래와 같다.

| 항목 | 한계 |
|---|---|
| DB 초기화 | 서버 실행 시 기존 데이터가 삭제될 수 있음 |
| seed 데이터 | 테스트용 소량 데이터 기준 |
| 실제 리뷰 누적 | 수집한 리뷰를 지속적으로 저장하는 구조 미완성 |
| 중복 방지 | `review_id` 기준 insert 중복 방지 로직 필요 |
| RTI 결과 저장 | `review_trust_scores` 테이블은 있으나 저장/재사용 로직 미완성 |
| migration | 스키마 변경 시 버전 관리 방식 미정 |

---

## 4. v1 DB 개선 목표

v1에서는 아래 목표를 기준으로 DB 구조를 개선한다.

- 기존 DB 데이터 유지
- seed 데이터와 실제 데이터 분리
- 실제 리뷰 데이터 insert 구조 설계
- `review_id` 기준 중복 저장 방지
- `product_id` / `product_url` 기준 상품 조회 안정화
- `review_date` 기준 trend 계산 유지
- RTI 결과 저장 여부 결정
- 추후 migration 방식 도입 검토

---

## 5. DB 초기화 방식 개선

### 5.1 v0 방식

v0에서는 테스트 편의를 위해 서버 실행 시 DB 테이블을 DROP 후 재생성할 수 있다.

```txt
DROP TABLE IF EXISTS review_trust_scores
DROP TABLE IF EXISTS reviews
DROP TABLE IF EXISTS products
```

이 방식은 테스트에는 편리하지만, 실제 리뷰 데이터가 쌓이는 v1에서는 사용할 수 없다.

---

### 5.2 v1 방식

v1에서는 서버 실행 시 기존 DB 데이터를 삭제하지 않는다.

권장 흐름은 아래와 같다.

```txt
서버 실행
→ 테이블 존재 여부 확인
→ 없으면 생성
→ 있으면 유지
→ 새 데이터만 insert
```

즉, v1에서는 `DROP TABLE`을 제거하고 `CREATE TABLE IF NOT EXISTS` 방식으로 변경한다.

예상 방향:

```sql
CREATE TABLE IF NOT EXISTS products (...);
CREATE TABLE IF NOT EXISTS reviews (...);
CREATE TABLE IF NOT EXISTS review_trust_scores (...);
```

---

## 6. seed 데이터와 실제 데이터 분리

v0에서는 seed 데이터가 `main.py` 내부에 직접 포함되어 있었다.

v1에서는 seed 데이터와 실제 데이터를 분리한다.

### 6.1 seed 데이터

seed 데이터는 테스트 또는 개발 초기 확인용으로만 사용한다.

권장 위치:

```txt
data/seed/
```

예시:

```txt
data/seed/products_seed.json
data/seed/reviews_seed.json
```

---

### 6.2 실제 리뷰 데이터

실제 리뷰 데이터는 팀원들과 수집한 후 DB에 insert한다.

권장 위치:

```txt
data/raw/
data/normalized/
```

예시:

```txt
data/raw/reviews_7195971829.json
data/normalized/reviews.json
```

---

## 7. products 테이블 설계 기준

v1에서 `products` 테이블은 상품 단위 조회의 기준이 된다.

필수 필드는 아래와 같다.

| 필드명 | 타입 | 설명 |
|---|---|---|
| `product_id` | String | 상품 고유 식별자 |
| `name` | String | 상품명 |
| `product_url` | String | 상품 URL |
| `category` | String | 상품 카테고리 |
| `created_at` | Timestamp | 생성 시각 |

v1 초기에는 `category`를 RTI 계산에 직접 반영하지 않는다.  
카테고리는 상품 메타데이터로 관리하고, 추후 데이터가 충분히 쌓이면 카테고리별 분석 기준 또는 가중치 조정을 검토한다.

---

## 8. reviews 테이블 설계 기준

v1에서 `reviews` 테이블은 AI 분석의 핵심 입력 데이터이다.

필수 필드는 아래와 같다.

| 필드명 | 타입 | 설명 |
|---|---|---|
| `review_id` | String | 리뷰 고유 식별자 |
| `product_id` | String | 상품 고유 식별자 |
| `user_id` | String | 작성자 ID 또는 마스킹 ID |
| `rating` | Integer | 별점 |
| `content` | Text | 리뷰 원문 |
| `review_date` | Date | 리뷰 작성일 |
| `verified_purchase` | String 또는 Boolean | 구매 인증 여부 |
| `reviews_written_today` | Integer | 당일 리뷰 작성 수 |
| `similar_review_count` | Integer | 유사 리뷰 수 |
| `created_at` | Timestamp | DB 저장 시각 |

추가로 가능하면 아래 필드도 관리한다.

| 필드명 | 설명 |
|---|---|
| `image_count` | 첨부 이미지 개수 |
| `quality_score` | 리뷰 품질 점수 |
| `repurchase` | 재구매 여부 |
| `free_trial` | 체험단 여부 |

---

## 9. content 처리 기준

리뷰 원문인 `content`는 API Request로 직접 전달하지 않는다.

`content`는 DB의 `reviews` 테이블에서 관리한다.

AI 서버는 `TriggerRequest`로 받은 `product_id` 또는 `url`을 기준으로 DB에서 리뷰를 조회하고, `reviews.content` 값을 사용하여 RTI를 계산한다.

즉, v1 기준 역할은 아래와 같다.

```txt
TriggerRequest
→ product_id / url 전달

DB reviews
→ content 보유

AI 분석
→ DB의 content 사용
```

---

## 10. product_id / product_url 매칭 기준

v1에서는 상품 조회 시 `product_id`를 우선 기준으로 사용한다.

기본 조회 흐름:

```txt
1. product_id로 products 테이블 조회
2. product_id가 없으면 url/page_url/product_url로 products.product_url 조회
3. 찾은 product_id로 reviews 테이블 조회
```

이 기준을 통해 백엔드가 `product_id` 또는 URL 중 어떤 값을 보내더라도 내부 DB에서 상품을 찾을 수 있도록 한다.

---

## 11. 리뷰 데이터 insert 기준

v1에서는 수집한 리뷰 데이터를 DB에 insert할 때 아래 기준을 따른다.

### 11.1 products insert

상품 데이터는 `product_id` 기준으로 중복을 방지한다.

```txt
이미 product_id가 존재하면 insert하지 않음
없으면 새 상품으로 insert
```

### 11.2 reviews insert

리뷰 데이터는 `review_id` 기준으로 중복을 방지한다.

```txt
이미 review_id가 존재하면 insert하지 않음
없으면 새 리뷰로 insert
```

이 기준을 통해 같은 리뷰가 여러 번 수집되더라도 DB에 중복 저장되지 않도록 한다.

---

## 12. review_trust_scores 저장 검토

v0에서는 API 요청 시마다 RTI를 실시간 계산하는 구조이다.

v1에서는 RTI 결과를 저장할지 검토한다.

### 12.1 실시간 계산 방식

장점:

- 구현이 단순함
- 최신 분석 로직을 항상 반영 가능

단점:

- 같은 리뷰를 반복 계산할 수 있음
- 리뷰 데이터가 많아질수록 API 응답이 느려질 수 있음

---

### 12.2 저장 후 조회 방식

장점:

- 한 번 계산한 결과를 재사용 가능
- API 응답 속도 개선 가능
- 분석 이력 관리 가능

단점:

- 분석 로직이 바뀌었을 때 재계산 필요
- 저장/갱신 정책이 필요함

---

### 12.3 저장 후보 필드

`review_trust_scores` 테이블에 저장할 후보 필드는 아래와 같다.

| 필드명 | 설명 |
|---|---|
| `score_id` | 점수 고유 ID |
| `review_id` | 분석 대상 리뷰 ID |
| `rti` | 최종 RTI 점수 |
| `level` | safe / warn / danger |
| `text_score` | 텍스트 신뢰 점수 |
| `behavior_score` | 행동 신뢰 점수 |
| `network_score` | 네트워크 신뢰 점수 |
| `reasons` | code/message 구조의 판단 사유 |
| `created_at` | 분석 결과 생성 시각 |

---

## 13. trend 계산 기준

v1에서도 trend는 `review_date`, `rti`, `level`을 기준으로 계산한다.

날짜별로 리뷰를 그룹화한 뒤 아래 값을 계산한다.

| 필드명 | 설명 |
|---|---|
| `date` | 집계 기준 일자 |
| `average_rti` | 해당 날짜 리뷰들의 평균 RTI |
| `review_count` | 해당 날짜 리뷰 수 |
| `safe_count` | safe 리뷰 수 |
| `warn_count` | warn 리뷰 수 |
| `danger_count` | danger 리뷰 수 |

현재는 일별 trend를 기준으로 한다.

시간대별 분석은 `review_datetime` 또는 시간 정보가 확보된 이후 확장한다.

---

## 14. v1 DB 작업 우선순위

### 1단계: DROP 구조 제거

- `DROP TABLE` 제거
- `CREATE TABLE IF NOT EXISTS` 방식으로 변경
- 기존 데이터 유지

### 2단계: seed 데이터 분리

- seed 데이터를 `main.py`에서 분리
- 테스트용 seed 파일 별도 관리

### 3단계: insert 구조 설계

- products insert 함수 설계
- reviews insert 함수 설계
- `product_id`, `review_id` 기준 중복 방지

### 4단계: RTI 결과 저장 검토

- 실시간 계산 유지 여부 검토
- `review_trust_scores` 저장 구조 설계
- 저장 후 조회 방식 도입 여부 결정

### 5단계: migration 방식 검토

- SQLite 기준 초기 migration 방식 검토
- 추후 Docker/DB 전환 시 migration 도구 적용 검토

---

## 15. v1 완료 기준

v1 DB 준비 작업의 완료 기준은 아래와 같다.

- DB DROP 구조 제거 방향 정리
- seed 데이터와 실제 데이터 분리 방향 정리
- products/reviews 필수 필드 정리
- `content` DB 관리 기준 확정
- `review_id` 기준 중복 방지 기준 확정
- `product_id` / `product_url` 매칭 기준 확정
- RTI 결과 저장 방식 후보 정리
- trend 계산 기준 정리

---

## 16. 결론

v1 DB 작업의 핵심은 테스트용 seed 구조에서 실제 리뷰 데이터 누적 구조로 전환하는 것이다.

v0에서는 Swagger 테스트와 데모를 위해 DB를 재생성하는 방식이 허용되었지만, v1에서는 수집한 리뷰 데이터가 유지되어야 한다.

따라서 v1에서는 DB 초기화 방식, 데이터 insert 방식, 중복 방지 기준, RTI 결과 저장 방식을 먼저 정리한 뒤 실제 리뷰 데이터 수집 및 모델 고도화 단계로 넘어간다.