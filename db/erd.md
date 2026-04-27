# Re:view DB ERD 초안

## 1. 전체 구조

Re:view AI + DB 파트에서는 다음 3개의 핵심 테이블을 사용합니다.

| 테이블명 | 역할 |
|---|---|
| products | 상품 정보 저장 |
| reviews | 정규화된 리뷰 데이터 저장 |
| review_trust_scores | AI 분석 결과 및 RTI 점수 저장 |

## 2. products 테이블

상품 정보를 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| product_id | VARCHAR(100) | 상품 ID |
| name | VARCHAR(500) | 상품명 |
| product_url | TEXT | 상품 URL |
| category1 | VARCHAR(100) | 1차 카테고리 |
| category2 | VARCHAR(100) | 2차 카테고리 |
| category3 | VARCHAR(100) | 3차 카테고리 |
| category4 | VARCHAR(100) | 4차 카테고리 |
| created_at | TIMESTAMP | 생성 시각 |

## 3. reviews 테이블

원본 데이터를 정규화한 리뷰 데이터를 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| review_id | VARCHAR(150) | 리뷰 ID |
| source | VARCHAR(50) | 원본 데이터 출처. 예: bin, hayeon |
| product_id | VARCHAR(100) | 상품 ID |
| user_id | VARCHAR(100) | 작성자 마스킹 ID |
| rating | INT | 별점 |
| content | TEXT | 리뷰 본문 |
| review_date | TIMESTAMP | 리뷰 작성일 |
| image_count | INT | 이미지 첨부 개수 |
| video_count | INT | 동영상 개수 |
| quality_score | DECIMAL(10, 6) | 리뷰 품질 점수 |
| verified_purchase | VARCHAR(20) | 구매 확인 여부. true / false / unknown |
| repurchase | VARCHAR(20) | 재구매 여부. true / false / unknown |
| free_trial | VARCHAR(20) | 체험단/무상 제공 여부. true / false / unknown |
| account_age_days | INT | 계정 생성 후 경과 일수. 현재 네이버 데이터에서는 null |
| reviews_written_today | INT | 같은 작성자의 같은 날짜 리뷰 수 |
| similar_review_count | INT | 유사 리뷰 수 |
| raw_json | TEXT | 원본 JSON 백업 |
| created_at | TIMESTAMP | 생성 시각 |

## 4. review_trust_scores 테이블

AI 분석 결과와 RTI 점수를 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| score_id | BIGINT | 점수 ID |
| review_id | VARCHAR(150) | 리뷰 ID |
| rti | INT | 최종 리뷰 신뢰도 점수 |
| level | VARCHAR(20) | safe / warn / danger |
| text_score | INT | 텍스트 분석 점수 |
| behavior_score | INT | 행동 패턴 점수 |
| network_score | INT | 네트워크 분석 점수 |
| input_features | TEXT | RTI 계산에 사용된 입력 특성 JSON |
| reasons | TEXT | 판단 사유 JSON 또는 문자열 |
| created_at | TIMESTAMP | 생성 시각 |

## 5. 테이블 관계

```txt
products 1 : N reviews
reviews 1 : 1 review_trust_scores
```

하나의 상품에는 여러 개의 리뷰가 연결될 수 있고, 하나의 리뷰에는 하나의 AI 신뢰도 분석 결과가 연결됩니다.

## 6. 데이터 흐름

```txt
data/raw/bin_reviews.json
data/raw/hayeon_reviews.txt
        ↓
ai/normalizer.py
        ↓
data/normalized/reviews.json
        ↓
reviews 테이블 저장
        ↓
ai/rti_scoring.py
        ↓
review_trust_scores 테이블 저장
```

## 7. v0 기준

현재 v0에서는 실제 AI 모델이 아니라 규칙 기반 mock scoring 방식을 사용합니다.

추후에는 다음과 같이 분석 코드를 모듈화할 예정입니다.

```txt
ai/text_analyzer.py
ai/behavior_analyzer.py
ai/network_analyzer.py
```

각 모듈이 텍스트, 행동, 네트워크 신호를 각각 분석하고, 최종적으로 `rti_scoring.py`에서 RTI 점수를 통합 산출합니다.