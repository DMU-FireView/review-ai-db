# Re:view AI Server v1 Development Plan

## 1. v1 목표

v1에서는 v0에서 구현한 Swagger 테스트/데모용 AI 서버 구조를 실제 리뷰 데이터 누적 및 분석 고도화 구조로 확장한다.

v0에서는 제한된 seed 데이터를 기반으로 `product_id`와 `url`을 통해 내부 DB에서 리뷰를 조회하고 RTI를 계산했다.

v1에서는 실제 리뷰 데이터가 들어왔을 때 이를 안정적으로 저장하고, 저장된 리뷰 데이터를 기반으로 RTI 분석 결과를 생성/저장할 수 있는 구조를 준비한다.

---

## 2. v0와 v1의 차이

### v0

- 테스트용 seed 데이터 사용
- Swagger 테스트 및 API 연동 구조 확인
- `product_id` / `url` 기반 TriggerRequest 사용
- API 요청 시 DB에서 리뷰를 조회하고 RTI를 실시간 계산
- `key_signal`, `patterns`, `tags`, `highlights` 제외

### v1

- 실제 리뷰 데이터 누적 저장 구조 준비
- DB DROP/seed 기반 테스트 구조 제거
- insert 또는 migration 기반 데이터 적재 방식 설계
- `review_id` 기준 중복 저장 방지
- RTI 결과 저장 방식 검토
- v0에서 제외한 확장 필드 단계적 도입

---

## 3. v1 데이터 흐름

v1 기준 데이터 흐름은 아래와 같다.

1. 정현님/백엔드가 네이버 검색 API 등을 통해 `product_id`와 `url` 확보
2. AI 서버는 `product_id` 또는 `product_url` 기준으로 내부 DB에서 상품 리뷰 조회
3. DB의 `reviews.content`를 기준으로 RTI 분석 수행
4. 분석 결과를 API 응답으로 반환
5. 필요 시 `review_trust_scores` 테이블에 RTI 결과 저장

---

## 4. content 처리 기준

리뷰 원문인 `content`는 API Request로 직접 전달하지 않는다.

`content`는 DB의 `reviews` 테이블에서 관리한다.

AI 서버는 `TriggerRequest`로 받은 `product_id` 또는 `url`을 기준으로 DB에서 리뷰를 조회하고, `reviews.content` 값을 사용하여 RTI를 계산한다.

---

## 5. v1 reviews 테이블 필수 필드

v1에서 `reviews` 테이블은 최소한 아래 필드를 포함해야 한다.

| 필드명 | 설명 |
|---|---|
| `review_id` | 리뷰 고유 식별자 |
| `product_id` | 상품 고유 식별자 |
| `user_id` | 작성자 ID 또는 마스킹 ID |
| `rating` | 별점 |
| `content` | 리뷰 원문 |
| `review_date` | 리뷰 작성일 |
| `verified_purchase` | 구매 인증 여부 |
| `reviews_written_today` | 당일 리뷰 작성 수 |
| `similar_review_count` | 유사 리뷰 수 |

추가로 가능하면 아래 필드도 관리한다.

- `image_count`
- `quality_score`
- `repurchase`
- `free_trial`

---

## 6. v1 products 테이블 필수 필드

| 필드명 | 설명 |
|---|---|
| `product_id` | 상품 고유 식별자 |
| `name` | 상품명 |
| `product_url` | 상품 URL |
| `category` | 상품 카테고리 |

v0에서는 `category`를 RTI 계산에 직접 반영하지 않는다.

v1에서도 초기에는 상품 메타데이터로만 관리하고, 추후 데이터가 충분히 쌓이면 카테고리별 분석 기준이나 가중치 조정을 검토한다.

---

## 7. DB 구조 개선 방향

현재 v0는 테스트 편의를 위해 서버 실행 시 DB 테이블을 DROP 후 재생성할 수 있다.

v1에서는 아래 방향으로 변경한다.

- 기존 DB 데이터 유지
- seed 데이터와 실제 데이터 분리
- 새 리뷰 데이터만 insert
- `review_id` 기준 중복 저장 방지
- `product_id` / `product_url` 기준 상품 매칭
- `review_date` 기준 trend 계산 유지

---

## 8. RTI 결과 저장 검토

v1에서는 RTI 결과를 매번 실시간 계산할지, 또는 DB에 저장 후 재사용할지 결정해야 한다.

저장할 경우 `review_trust_scores` 테이블을 활용한다.

저장 후보 필드는 아래와 같다.

| 필드명 | 설명 |
|---|---|
| `review_id` | 분석 대상 리뷰 ID |
| `rti` | 최종 RTI 점수 |
| `level` | safe / warn / danger |
| `text_score` | 텍스트 신뢰 점수 |
| `behavior_score` | 행동 신뢰 점수 |
| `network_score` | 네트워크 신뢰 점수 |
| `reasons` | code/message 구조의 판단 사유 |
| `created_at` | 분석 결과 생성 시각 |

---

## 9. v1 확장 필드

v0에서 제외한 아래 필드는 v1에서 단계적으로 도입한다.

| 필드 | 도입 방향 |
|---|---|
| `tags` | `reasons.message` 기반 화면용 태그 생성 |
| `key_signal` | 상품 단위 `reasons.code` 집계 후 대표 사유 선정 |
| `highlights` | 리뷰 본문에서 의심 표현 구간 추출 |
| `patterns` | 상품 단위 시간대 집중, 유사 리뷰 반복, 특정 표현 반복 분석 |

---

## 10. v1 우선순위

### 1단계

- DB DROP 구조 제거 계획 정리
- seed 데이터와 실제 데이터 분리
- insert 기반 데이터 적재 방식 설계

### 2단계

- `review_id` 기준 중복 저장 방지
- `product_id` / `product_url` 기준 조회 안정화
- 실제 데이터가 들어왔을 때 저장 가능한 구조 준비

### 3단계

- RTI 결과 저장 여부 결정
- `review_trust_scores` 저장 구조 설계
- 실시간 계산 방식과 저장 후 조회 방식 비교

### 4단계

- `tags` 생성 로직 설계
- `key_signal` 생성 로직 설계

### 5단계

- `highlights` 설계
- `patterns` 설계

---

## 11. 완료 기준

- v1 데이터 흐름 정리
- DB 누적 저장 방향 정리
- `content` DB 관리 기준 확정
- reviews/products 필수 필드 정리
- RTI 결과 저장 방식 후보 정리
- v1 확장 필드 도입 순서 정리