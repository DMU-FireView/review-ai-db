# Re:view DB ERD 초안

## 1. 전체 구조

Re:view AI + DB 파트에서는 다음 3개의 핵심 테이블을 사용합니다.

| 테이블명 | 역할 |
|---|---|
| products | 상품 정보 저장 |
| reviews | 리뷰 원문 및 분석 입력값 저장 |
| review_trust_scores | AI 분석 결과 및 RTI 점수 저장 |

## 2. products 테이블

상품 정보를 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| product_id | VARCHAR(50) | 상품 ID |
| name | VARCHAR(255) | 상품명 |
| category | VARCHAR(100) | 상품 카테고리 |
| created_at | TIMESTAMP | 생성 시각 |

## 3. reviews 테이블

리뷰 원문과 AI 분석에 필요한 입력값을 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| review_id | BIGINT | 리뷰 ID |
| product_id | VARCHAR(50) | 상품 ID |
| user_id | VARCHAR(100) | 작성자 ID |
| rating | INT | 별점 |
| content | TEXT | 리뷰 본문 |
| verified_purchase | BOOLEAN | 구매 확인 여부 |
| account_age_days | INT | 계정 생성 후 경과 일수 |
| reviews_written_today | INT | 하루 작성 리뷰 수 |
| similar_review_count | INT | 유사 리뷰 수 |
| created_at | TIMESTAMP | 생성 시각 |

## 4. review_trust_scores 테이블

AI 분석 결과와 RTI 점수를 저장합니다.

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| score_id | BIGINT | 점수 ID |
| review_id | BIGINT | 리뷰 ID |
| rti | INT | 최종 리뷰 신뢰도 점수 |
| level | VARCHAR(20) | safe / warn / danger |
| text_score | INT | 텍스트 분석 점수 |
| behavior_score | INT | 행동 패턴 점수 |
| network_score | INT | 네트워크 분석 점수 |
| reasons | TEXT | 판단 사유 |
| created_at | TIMESTAMP | 생성 시각 |

## 5. 테이블 관계

products 1 : N reviews

reviews 1 : 1 review_trust_scores

즉, 하나의 상품에는 여러 개의 리뷰가 연결될 수 있고, 하나의 리뷰에는 하나의 AI 신뢰도 분석 결과가 연결됩니다.
