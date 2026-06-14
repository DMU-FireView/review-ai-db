# NAVER RTI 결과와 review_trust_scores 매핑 초안

## 문서 목적

이 문서는 네이버 상품 리뷰 크롤링 결과를 RTI 분석한 출력 JSON이 이후 DB의 `review_trust_scores` 테이블에 어떻게 매핑될 수 있는지 정리한 초안이다.

현재 검증된 범위와 향후 저장 흐름을 연결하기 위한 팀 협의용 문서이며, DB insert, API, Redis/Worker, Spring 연동 구현을 포함하지 않는다. 아래 DB 컬럼명과 저장 정책은 실제 스키마 및 팀 협의에 따라 변경될 수 있다.

## 1. 현재 검증된 흐름

현재 네이버 상품 URL 1개를 기준으로 다음 흐름까지 검증되었다.

1. Playwright 크롤러가 네이버 상품 페이지에서 리뷰 관련 API body를 캡처한다.
2. 캡처한 JSON 내부에서 리뷰 배열을 탐색한다.
3. 탐색한 리뷰를 공통 raw review schema로 매핑한다.
4. `analyze_crawled_naver_reviews.py`가 raw JSON을 읽는다.
5. 리뷰별 RTI 점수, `level`, `reasons`, `signals`를 산출한다.
6. 결과를 `output/naver_rti_results_<product_id>.json`에 저장한다.

분석 스크립트는 기존 text/behavior/network 분석 함수와 40/35/25 가중치 흐름을 재사용한다. 이 과정에서는 DB, API, Redis 및 외부 감성 API를 호출하지 않는다.

## 2. 입력 raw JSON 구조

RTI 분석 스크립트의 입력으로 사용하는 raw JSON의 예시는 다음과 같다.

```json
{
  "source": "naver",
  "mall": "NAVER",
  "product": {
    "product_id": "7195971829",
    "product_name": "unknown",
    "product_url": "https://brand.naver.com/hera/products/7195971829",
    "category": "unknown"
  },
  "reviews": [
    {
      "review_id": "naver_7195971829_0",
      "user_id": "unknown",
      "rating": 5,
      "content": "리뷰 내용",
      "review_date": "unknown",
      "image_count": 0,
      "images": []
    }
  ]
}
```

`product`에는 분석 대상 상품 정보가 들어가며, `reviews`에는 RTI 분석 단위가 되는 개별 리뷰가 배열로 저장된다.

## 3. RTI 결과 JSON 구조

RTI 분석 결과 JSON의 예시는 다음과 같다.

```json
{
  "source": "naver",
  "product": {
    "product_id": "7195971829",
    "product_name": "unknown",
    "product_url": "https://brand.naver.com/hera/products/7195971829",
    "category": "unknown"
  },
  "review_count": 30,
  "analyzed_count": 30,
  "skipped_count": 0,
  "results": [
    {
      "review_id": "naver_7195971829_0",
      "user_id": "unknown",
      "rating": 5,
      "content": "리뷰 내용",
      "review_date": "unknown",
      "rti_score": 82,
      "level": "safe",
      "reasons": [],
      "signals": {}
    }
  ]
}
```

상위 필드에는 상품 정보와 전체 처리 건수가 저장되고, `results`에는 리뷰별 RTI 분석 결과가 저장된다. DB 저장 후보가 되는 핵심 값은 `review_id`, `rti_score`, `level`, `reasons`, `signals`이다.

## 4. review_trust_scores 매핑 초안

| RTI result field | DB column candidate | 설명 | 비고 |
| --- | --- | --- | --- |
| `results[].review_id` | `review_id` | RTI 분석 대상 리뷰를 식별하고 `reviews` 테이블의 리뷰와 연결하는 값 | 참조 무결성 및 중복 방지 기준 후보 |
| `results[].rti_score` 또는 `rti` | `trust_score` 또는 `rti_score` | 리뷰의 최종 RTI 점수 | 애플리케이션 내 명칭 통일 필요 |
| `results[].level` | `trust_level` 또는 `level` | RTI 점수에 따른 신뢰 수준 | 허용 값 정의 필요 |
| `results[].reasons` | `reasons_json` 또는 `reason_summary` | 해당 점수와 level이 산출된 사유 | JSON 원문 또는 요약 저장 방식 협의 필요 |
| `results[].signals` | `signals_json` | text/behavior/network 분석에서 생성된 세부 신호 | JSON 또는 TEXT 저장 방식 협의 필요 |
| 저장 시각 | `created_at` | 최초 RTI 결과 저장 시각 | `NOW()` 사용 후보 |
| 갱신 시각 | `updated_at` | RTI 결과가 갱신된 시각 | `NOW()` 사용 후보 |

위 표는 매핑 후보이며 실제 `review_trust_scores` 컬럼명은 팀 협의와 최종 DB 스키마 확인 후 확정해야 한다.

## 5. reviews 테이블과의 관계

- RTI 점수는 개별 `review_id` 기준으로 저장하는 것이 자연스럽다.
- `reviews` 테이블에 해당 `review_id`가 먼저 저장되어 있어야 `review_trust_scores`가 이를 참조할 수 있다.
- 같은 `review_id`에 대한 RTI 결과의 중복 저장은 피해야 한다.
- MVP에서는 이미 저장된 `review_id`의 리뷰와 RTI 결과를 skip하고, DB에 없는 신규 `review_id`만 저장 및 분석한다.

기본 관계는 다음과 같이 예상할 수 있다.

```text
reviews.review_id
→ review_trust_scores.review_id
```

실제 외래 키 사용 여부와 1:1 또는 이력 관리를 포함한 관계 형태는 최종 DB 스키마에서 확정한다.

## 6. 중복 저장 정책 확정안

MVP의 중복 저장 여부는 상품 단위가 아니라 크롤링 결과에 포함된 각 `review_id` 단위로 판단한다.

```text
각 리뷰의 review_id 기준으로 기존 저장 여부 확인
├─ DB에 없는 review_id
│  → reviews insert
│  → RTI 분석
│  → review_trust_scores insert
└─ DB에 이미 있는 review_id
   → 중복 저장 방지를 위해 skip
```

상품에 저장된 리뷰가 하나라도 있다는 이유로 해당 상품의 크롤링 결과 전체를 skip하지 않는다. 기존 리뷰와 신규 리뷰를 구분하여 신규 `review_id`만 저장 및 분석한다.

### 정책 이유

- 상품 단위로 전체 skip하면 이후 해당 상품에 새로 추가된 리뷰를 놓칠 수 있다.
- `review_id` 단위로 판단하면 기존 리뷰는 중복 저장하지 않으면서 신규 리뷰는 추가 수집할 수 있다.
- 신규 여부를 기준으로 insert와 분석을 결정하므로 MVP 단계에서 구현이 단순하고 안정적이다.
- 리뷰별 RTI 결과를 조회하고 재사용하는 Saved RTI 구조와도 잘 맞는다.

### MVP 이후 확장 고려사항

MVP에서는 기존 `review_id`의 리뷰 내용이 수정된 경우까지 즉시 감지하고 반영하는 기능은 제외한다. 리뷰 수정 반영이 필요해지면 다음 방식을 검토한다.

- `content_hash`를 기준으로 기존 리뷰 내용의 변경 여부 확인
- `review_updated_at`을 기준으로 변경 여부 확인
- 변경된 리뷰만 RTI 재분석
- 변경 이력 관리가 필요하면 `review_trust_scores_history` 같은 별도 테이블 고려

## 7. 저장 타이밍

FastAPI Worker 기준으로 예상하는 MVP 저장 흐름은 다음과 같다.

1. Queue job 수신
2. `productUrl` 기준 크롤링
3. raw reviews 생성
4. 각 `review_id` 기준으로 기존 저장 여부 확인
5. 신규 `review_id`만 `reviews` insert
6. 신규 `review_id`만 RTI 분석
7. 신규 `review_id`만 `review_trust_scores` insert
8. 모든 신규 리뷰 처리 후 `product_analysis_job`을 `DONE`으로 처리

```text
Queue job
→ productUrl 기준 크롤링
→ raw reviews 생성
→ review_id별 기존 저장 여부 확인
→ 신규 리뷰만 reviews insert
→ 신규 리뷰만 RTI 분석
→ 신규 리뷰만 review_trust_scores insert
→ product_analysis_job DONE
```

이 흐름은 구현이 확정되거나 완료된 동작이 아니라 MVP 기준 협의안이다. 저장 주체, 트랜잭션 범위, 실패 처리 및 Spring과 FastAPI 사이의 책임 분리는 별도로 확정해야 한다.

## 8. 아직 협의 필요한 항목

- [ ] `review_trust_scores` 실제 컬럼명
- [ ] `trust_score`와 `rti_score` 명칭 통일
- [ ] `level` 값 정의: `safe` / `warning` / `danger` 등
- [ ] `reasons` 저장 방식: JSON / TEXT / 별도 테이블
- [ ] `signals` 저장 방식: JSON / TEXT
- [x] `review_id` 기준 중복 체크 방식은 MVP 기준으로 합의
- [x] 리뷰 수정 반영은 MVP 이후 `content_hash` / `review_updated_at` 기준으로 확장 검토
- [ ] FastAPI가 DB에 직접 insert/update할지, Spring을 경유할지
- [ ] 실패 시 부분 저장 허용 여부

## 9. 현재 단계 결론

현재는 네이버 상품 URL 1개 기준으로 크롤링된 리뷰 30개를 RTI 분석 결과 JSON으로 변환하는 것까지 검증되었다.

MVP의 중복 저장 정책은 상품 단위 전체 skip이 아니라 `review_id` 단위 확인 후 신규 리뷰만 저장 및 분석하는 방식으로 합의되었다. 다음 단계는 이 결과 JSON을 DB 저장 구조와 연결하기 전에 팀과 `review_trust_scores`의 실제 컬럼명, 저장 주체 및 실패 처리 정책을 확정하는 것이다.
