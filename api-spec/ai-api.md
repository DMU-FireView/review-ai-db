# AI 분석 API 명세

이 문서는 정현님 Spring Boot 서버와 동환님 서버 파트에서 AI 분석 결과를 사용할 수 있도록 요청/응답 형식을 정리한 문서입니다.

## 1. 목적

AI + DB 파트에서는 리뷰 데이터를 입력받아 다음 결과를 반환합니다.

- RTI 점수
- safe / warn / danger 등급
- 텍스트 점수
- 행동 패턴 점수
- 네트워크 점수
- 판단 사유 목록

## 2. 리뷰 분석 요청

Endpoint 예시:

POST /api/ai/reviews/analyze

## 3. Request Body

{
  "review_id": 1,
  "user_id": "reviewer_0099",
  "product_id": "p001",
  "rating": 5,
  "content": "이 제품 정말 최고예요. 품질 완전 대박...",
  "verified_purchase": false,
  "account_age_days": 2,
  "reviews_written_today": 12,
  "similar_review_count": 8
}

## 4. Request Field 설명

| 필드명 | 타입 | 설명 |
|---|---|---|
| review_id | number | 리뷰 ID |
| user_id | string | 작성자 ID |
| product_id | string | 상품 ID |
| rating | number | 별점 |
| content | string | 리뷰 본문 |
| verified_purchase | boolean | 구매 확인 여부 |
| account_age_days | number | 계정 생성 후 경과 일수 |
| reviews_written_today | number | 하루 작성 리뷰 수 |
| similar_review_count | number | 유사 리뷰 수 |

## 5. Response Body

{
  "review_id": 1,
  "user_id": "reviewer_0099",
  "product_id": "p001",
  "rti": 28,
  "level": "danger",
  "signals": {
    "text": 25,
    "behavior": 15,
    "network": 50
  },
  "reasons": [
    "반복 표현 탐지: '대박' 2회",
    "구매 이력 미확인",
    "계정 생성 직후 리뷰 작성",
    "유사 리뷰 네트워크 군집 탐지"
  ]
}

## 6. Response Field 설명

| 필드명 | 타입 | 설명 |
|---|---|---|
| review_id | number | 리뷰 ID |
| user_id | string | 작성자 ID |
| product_id | string | 상품 ID |
| rti | number | 최종 리뷰 신뢰도 점수 |
| level | string | safe / warn / danger |
| signals.text | number | 텍스트 분석 점수 |
| signals.behavior | number | 행동 패턴 점수 |
| signals.network | number | 네트워크 분석 점수 |
| reasons | string[] | 감점 또는 판단 사유 |

## 7. level 기준

| level | 조건 | 설명 |
|---|---|---|
| safe | RTI 80 이상, 감점 사유 없음 | 신뢰 가능 리뷰 |
| warn | RTI 50 이상 또는 감점 사유 존재 | 의심 리뷰 |
| danger | RTI 50 미만 | 위험 리뷰 |

## 8. 백엔드 저장 권장 테이블

AI 분석 결과는 review_trust_scores 테이블에 저장하는 것을 권장합니다.

저장 대상:

- review_id
- rti
- level
- text_score
- behavior_score
- network_score
- reasons
