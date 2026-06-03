# Re:view AI Server v1 Data Ingestion Plan

## 1. 목적

v1에서는 실제 리뷰 데이터가 수집되었을 때 이를 AI 서버가 사용할 수 있는 형태로 정규화하고 DB에 적재하는 구조를 준비한다.

v0에서는 seed 데이터 기반으로 Swagger 테스트를 진행했지만, v1에서는 팀원들이 수집한 리뷰 데이터를 안정적으로 저장하고 분석할 수 있어야 한다.

본 문서는 raw review data를 normalized review data로 변환하고, 이를 DB에 insert하는 흐름을 정리한다.

---

## 2. v1 데이터 적재 흐름

v1 기준 데이터 적재 흐름은 아래와 같다.

```txt
raw review data
→ normalizer
→ normalized reviews
→ DB insert
→ RTI analyzer
→ review_trust_scores 저장 검토
```

---

## 3. raw 데이터 기준

팀원들이 수집하는 raw 데이터는 출처에 따라 필드명이 다를 수 있다.

예시:

| 출처 | 상품 URL 필드 | 리뷰 본문 필드 |
|---|---|---|
| 빈님 데이터 | `page_url` | `content` |
| 하연 데이터 | `productUrl` | `reviewContent` |
| 최종 정규화 | `product_url` | `content` |

따라서 v1에서는 raw 데이터의 필드명이 달라도 최종적으로 동일한 normalized schema로 변환해야 한다.

---

## 4. normalized review schema

정규화 이후 리뷰 1개는 아래 구조를 기준으로 한다.

```json
{
  "source": "string",
  "review_id": "string",
  "product_id": "string",
  "product_url": "string",
  "product_name": "string",
  "category": "string",
  "user_id": "string",
  "rating": 5,
  "content": "리뷰 원문",
  "review_date": "2026-05-24",
  "image_count": 0,
  "quality_score": 0.75,
  "verified_purchase": "unknown",
  "repurchase": "unknown",
  "free_trial": "unknown",
  "reviews_written_today": 1,
  "similar_review_count": 0
}
```

---

## 5. 필수 필드

v1에서 반드시 유지해야 하는 필드는 아래와 같다.

| 필드명 | 설명 |
|---|---|
| `review_id` | 리뷰 고유 식별자 |
| `product_id` | 상품 고유 식별자 |
| `product_url` | 상품 URL |
| `user_id` | 작성자 ID 또는 마스킹 ID |
| `rating` | 별점 |
| `content` | 리뷰 원문 |
| `review_date` | 리뷰 작성일 |

이 필드들이 없으면 DB 저장, RTI 분석, trend 계산, 리뷰 조회가 어려워질 수 있다.

---

## 6. 선택 필드 및 기본값

아래 필드는 없을 수 있으므로 기본값을 설정한다.

| 필드명 | 기본값 |
|---|---|
| `image_count` | 0 |
| `quality_score` | null |
| `verified_purchase` | "unknown" |
| `repurchase` | "unknown" |
| `free_trial` | "unknown" |
| `reviews_written_today` | 1 |
| `similar_review_count` | 0 |
| `category` | null 또는 "unknown" |

---

## 7. 필드 매핑 기준

### 7.1 상품 URL

상품 URL은 아래 순서로 읽는다.

```txt
product_url
→ page_url
→ productUrl
→ url
```

최종 필드는 `product_url`로 통일한다.

---

### 7.2 리뷰 본문

리뷰 본문은 아래 순서로 읽는다.

```txt
content
→ reviewContent
→ review_content
```

최종 필드는 `content`로 통일한다.

---

### 7.3 리뷰 날짜

리뷰 날짜는 아래 순서로 읽는다.

```txt
review_date
→ reviewDate
→ created_at
```

최종 필드는 `review_date`로 통일한다.

날짜 포맷은 아래 형식을 기준으로 한다.

```txt
YYYY-MM-DD
```

---

## 8. DB insert 기준

정규화된 데이터는 DB에 insert한다.

### 8.1 products insert

상품 정보는 `product_id` 기준으로 중복을 방지한다.

```txt
product_id가 이미 존재하면 skip
product_id가 없으면 insert
```

저장 필드:

- `product_id`
- `name`
- `product_url`
- `category`

---

### 8.2 reviews insert

리뷰 정보는 `review_id` 기준으로 중복을 방지한다.

```txt
review_id가 이미 존재하면 skip
review_id가 없으면 insert
```

저장 필드:

- `review_id`
- `product_id`
- `user_id`
- `rating`
- `content`
- `review_date`
- `verified_purchase`
- `reviews_written_today`
- `similar_review_count`
- `image_count`
- `quality_score`
- `repurchase`
- `free_trial`

---

## 9. 중복 처리 기준

v1에서는 동일한 리뷰가 여러 번 수집될 수 있으므로 중복 방지가 필요하다.

중복 판단 1순위:

```txt
review_id
```

보조 기준:

```txt
product_id + user_id + content + review_date
```

단, v1 초기에는 `review_id` 기준 중복 방지를 우선 적용한다.

---

## 10. 검증 기준

DB insert 전 아래 항목을 검증한다.

| 검증 항목 | 기준 |
|---|---|
| `review_id` | 비어 있으면 저장하지 않음 |
| `product_id` | 비어 있으면 저장하지 않음 |
| `content` | 비어 있으면 RTI 분석 불가 |
| `review_date` | 비어 있으면 trend 계산 불가 |
| `rating` | 숫자로 변환 가능해야 함 |

---

## 11. 에러 처리 방향

v1에서는 일부 데이터가 불완전할 수 있으므로 에러 처리 기준이 필요하다.

| 상황 | 처리 방향 |
|---|---|
| 필수 필드 누락 | 해당 리뷰 skip |
| 선택 필드 누락 | 기본값 적용 |
| 날짜 포맷 오류 | 변환 시도 후 실패 시 skip 또는 null 처리 |
| rating 변환 실패 | 기본값 0 또는 skip 검토 |
| 중복 review_id | insert skip |

---

## 12. output 파일 관리

정규화 결과는 DB insert 전 확인을 위해 파일로 저장할 수 있다.

권장 경로:

```txt
data/normalized/reviews.json
```

RTI 분석 결과는 아래 경로에 저장할 수 있다.

```txt
output/rti_results.json
output/rti_results_sample.json
```

단, v1에서는 최종적으로 DB 저장 구조로 전환하는 것을 목표로 한다.

---

## 13. 완료 기준

v1 데이터 적재 준비의 완료 기준은 아래와 같다.

- raw 데이터 필드 차이 정리
- normalized schema 확정
- 필수 필드와 선택 필드 구분
- product_url/content/review_date 매핑 기준 정리
- DB insert 기준 정리
- 중복 처리 기준 정리
- 검증 및 에러 처리 방향 정리

---

## 14. 결론

v1 데이터 적재 작업의 핵심은 출처가 다른 리뷰 데이터를 하나의 normalized schema로 통일하는 것이다.

이를 통해 AI 서버는 데이터 출처와 상관없이 동일한 구조로 리뷰를 분석할 수 있다.

실제 리뷰 데이터 수집이 시작되면 본 기준에 맞춰 normalizer와 DB insert 흐름을 구현한다.