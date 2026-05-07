# AI 분석 API 명세

이 문서는 백엔드/서버가 AI 분석 결과를 사용할 때 필요한 데이터 형식을 정의합니다.

## 1. 목적

AI + DB 파트에서는 원본 리뷰 데이터를 공통 포맷으로 정규화한 뒤 RTI를 계산합니다.

AI 분석 결과에는 다음 정보가 포함됩니다.

- RTI 점수
- safe / warn / danger 등급
- 텍스트 점수
- 행동 패턴 점수
- 네트워크 점수
- RTI 계산에 사용된 입력 특성
- 판단 사유 목록

## 2. 데이터 처리 흐름

```txt
data/raw/bin_reviews.json
data/raw/hayeon_reviews.txt
        ↓
ai/normalizer.py
        ↓
data/normalized/reviews.json
        ↓
ai/rti_scoring.py
        ↓
output/rti_results.json
```

## 3. 리뷰 분석 요청

Endpoint 예시:

```txt
POST /api/ai/reviews/analyze
```

## 4. Request Body

```json
{
  "source": "bin",
  "review_id": "4879548868-ncp_1nucl1_01-11590446932",
  "product_id": "53530143052",
  "product_name": "로랜텍 커널형 버즈 무선 블루투스 이어폰",
  "product_url": "https://example.com/product/53530143052",
  "user_id": "bouo****",
  "rating": 5,
  "content": "굉장히 작고 귀엽고 가볍습니다...",
  "review_date": "2026-01-07",
  "image_count": 3,
  "images": [],
  "video_count": 0,
  "quality_score": 0.761338,
  "topics": [],
  "verified_purchase": "unknown",
  "repurchase": "unknown",
  "free_trial": "unknown",
  "account_age_days": null,
  "reviews_written_today": 1,
  "similar_review_count": 0
}
```

## 5. Request Field 설명

| 필드명 | 타입 | 설명 |
|---|---|---|
| source | string | 원본 데이터 출처. 예: bin, hayeon |
| review_id | string/number | 리뷰 ID |
| product_id | string/number | 상품 ID |
| product_name | string | 상품명 |
| product_url | string/null | 상품 URL |
| user_id | string | 작성자 마스킹 ID |
| rating | number | 별점 |
| content | string | 리뷰 본문 |
| review_date | string/null | 리뷰 작성일 |
| image_count | number | 이미지 첨부 개수 |
| images | array | 이미지 URL 목록 |
| video_count | number | 동영상 개수 |
| quality_score | number/null | 리뷰 품질 점수. 없으면 null |
| topics | array | 리뷰 토픽 또는 분석 태그 |
| verified_purchase | boolean/string | 구매 확인 여부. 확인 불가 시 unknown |
| repurchase | boolean/string | 재구매 여부. 확인 불가 시 unknown |
| free_trial | boolean/string | 체험단/무상 제공 여부. 확인 불가 시 unknown |
| account_age_days | number/null | 계정 생성 후 경과 일수. 현재 네이버 데이터에서는 null |
| reviews_written_today | number/null | 같은 작성자의 같은 날짜 리뷰 수 |
| similar_review_count | number | 유사 리뷰 수 |

## 6. Response Body

```json
{
  "source": "bin",
  "review_id": "4879548868-ncp_1nucl1_01-11590446932",
  "user_id": "bouo****",
  "product_id": "53530143052",
  "product_name": "로랜텍 커널형 버즈 무선 블루투스 이어폰",
  "rating": 5,
  "review_date": "2026-01-07",
  "rti": 92,
  "level": "safe",
  "signals": {
    "text": 100,
    "behavior": 90,
    "network": 100
  },
  "input_features": {
    "image_count": 3,
    "quality_score": 0.761338,
    "verified_purchase": "unknown",
    "repurchase": "unknown",
    "free_trial": "unknown",
    "reviews_written_today": 1,
    "similar_review_count": 0
  },
  "reasons": [
    "구매 여부 확인 불가"
  ]
}
```

## 7. Response Field 설명

| 필드명 | 타입 | 설명 |
|---|---|---|
| source | string | 원본 데이터 출처 |
| review_id | string/number | 리뷰 ID |
| user_id | string | 작성자 마스킹 ID |
| product_id | string/number | 상품 ID |
| product_name | string | 상품명 |
| rating | number | 별점 |
| review_date | string/null | 리뷰 작성일 |
| rti | number | 최종 리뷰 신뢰도 점수 |
| level | string | safe / warn / danger |
| signals.text | number | 텍스트 분석 점수 |
| signals.behavior | number | 행동 패턴 점수 |
| signals.network | number | 네트워크 분석 점수 |
| input_features | object | RTI 계산에 사용된 입력 특성 |
| reasons | string[] | 감점 또는 판단 사유 |

## 8. level 기준

| level | 조건 | 설명 |
|---|---|---|
| safe | RTI 80 이상, 주요 감점 사유 없음 | 신뢰 가능 리뷰 |
| warn | RTI 50 이상 또는 감점 사유 존재 | 의심 필요 리뷰 |
| danger | RTI 50 미만 | 위험 리뷰 가능성 높음 |

## 9. 백엔드 저장 권장 테이블

AI 분석 결과는 `review_trust_scores` 테이블에 저장하는 것을 권장합니다.

저장 대상:

- review_id
- rti
- level
- text_score
- behavior_score
- network_score
- input_features
- reasons

## 10. v0 기준

현재 v0에서는 실제 AI 모델이 아니라 규칙 기반 mock scoring 방식을 사용합니다.

추후에는 다음과 같이 분석 코드를 모듈화되어 있습니다.

```txt
ai/text_analyzer.py
ai/behavior_analyzer.py
ai/network_analyzer.py
```

각 모듈이 개별 점수를 계산하고, `rti_scoring.py`에서 최종 RTI를 통합 산출하는 구조로 확장합니다.

## 11. Cloud Natural Language API 연결 준비 상태

Text Score 계산에는 추후 Google Cloud Natural Language API 감성 분석 결과를 보조 신호로 반영할 예정입니다.

현재는 실제 API 호출이 아니라, 연결 준비용 fallback 구조만 추가된 상태입니다.

추가된 파일은 다음과 같습니다.

```txt
ai/sentiment_client.py
```

현재 기본 동작은 다음과 같습니다.

```txt
ENABLE_CLOUD_NLP=false
```

이 상태에서는 Google Cloud Natural Language API를 실제로 호출하지 않고, mock/fallback 감성 분석 결과를 반환합니다.

따라서 현재 서버 연동 시에는 기존 RTI 응답 구조를 그대로 사용하면 됩니다.

현재 응답 구조:

```json
{
  "review_id": "4879548868-ncp_1nucl1_01-11590446932",
  "product_id": "53530143052",
  "rti": 92,
  "level": "warn",
  "signals": {
    "text": 90,
    "behavior": 90,
    "network": 100
  },
  "input_features": {
    "image_count": 3,
    "quality_score": 0.761338,
    "verified_purchase": "unknown",
    "repurchase": "unknown",
    "free_trial": "unknown",
    "reviews_written_today": 1,
    "similar_review_count": 0
  },
  "reasons": [
    "구매 여부 확인 불가"
  ]
}
```

추후 실제 Google Cloud Natural Language API 연결 후에는 `signals.text` 계산 과정에 sentiment score / magnitude가 보조 신호로 반영될 수 있습니다.

다만 서버 응답 필드 구조는 최대한 유지하고, 필요한 경우 `input_features` 또는 별도 필드에 sentiment 결과를 추가하는 방식으로 확장할 예정입니다.

## 12. RTI 결과 샘플 파일

서버/프론트 연동 참고용 RTI 결과 샘플은 아래 파일에서 확인할 수 있습니다.

```txt
output/rti_results_sample.json
```

전체 RTI 분석 결과는 아래 파일에 저장됩니다.

```txt
output/rti_results.json
```

현재 v0에서는 네이버 데이터에서 구매 확인 여부가 명확하지 않은 경우가 많아 `verified_purchase`가 `unknown`으로 처리됩니다.

이로 인해 샘플 결과에서도 `구매 여부 확인 불가` 사유가 포함되고, `warn` 등급이 많이 나올 수 있습니다.

샘플 파일은 전체 결과 중 일부만 추출한 파일이며, 서버/프론트에서 응답 구조를 확인하기 위한 참고용입니다.

샘플 데이터의 주요 필드는 다음과 같습니다.

| 필드명 | 설명 |
|---|---|
| `review_id` | 리뷰 ID |
| `product_id` | 상품 ID |
| `product_name` | 상품명 |
| `user_id` | 작성자 마스킹 ID |
| `rating` | 별점 |
| `review_date` | 리뷰 작성일 |
| `rti` | 최종 리뷰 신뢰도 점수 |
| `level` | `safe / warn / danger` 등급 |
| `signals` | text / behavior / network 점수 |
| `input_features` | RTI 계산에 사용된 입력 특성 |
| `reasons` | 판단 사유 목록 |

예시 구조:

```json
{
  "source": "bin",
  "review_id": "4879548868-ncp_1nucl1_01-11590446932",
  "user_id": "bouo****",
  "product_id": "53530143052",
  "product_name": "로랜텍 커널형 버즈 무선 블루투스 이어폰 RSM-R510",
  "rating": 5,
  "review_date": "2026-01-07",
  "rti": 92,
  "level": "warn",
  "signals": {
    "text": 90,
    "behavior": 90,
    "network": 100
  },
  "input_features": {
    "image_count": 3,
    "quality_score": 0.761338,
    "verified_purchase": "unknown",
    "repurchase": "unknown",
    "free_trial": "unknown",
    "reviews_written_today": 1,
    "similar_review_count": 0
  },
  "reasons": [
    "과도한 느낌표 사용",
    "구매 여부 확인 불가"
  ]
}
```