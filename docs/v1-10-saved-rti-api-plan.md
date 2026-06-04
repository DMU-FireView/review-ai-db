# v1-10 Saved RTI Score API Connection Plan

## 1. 현재 문제

현재 v1-9까지의 saved RTI score 흐름은 아래까지 완료되어 있다.

```txt
reviews DB
-> scripts/save_rti_scores.py
-> review_trust_scores DB
-> ai/rti_score_repository.py
```

하지만 API 요청 처리 흐름에서는 product-detail 요청 때마다 `analyze_single_review()`가 다시 실행될 수 있다.

- 리뷰 수가 많아지면 API 응답 속도가 느려질 수 있다.
- 이후 KoELECTRA 같은 모델 추론이 붙으면 매 요청마다 재계산/재추론하는 방식의 비용과 지연 시간이 더 커질 수 있다.
- 이미 `review_trust_scores`에 저장된 RTI score가 있어도 API 응답에서 재사용하지 못하면 저장 파이프라인의 장점을 충분히 활용하지 못한다.

## 2. 목표

v1-10에서는 API 요청 시 저장된 RTI score가 있으면 먼저 사용하고, 없으면 기존 실시간 분석으로 fallback하는 구조를 설계한다.

- 저장된 RTI score가 있으면 우선 사용한다.
- 저장된 score가 없으면 기존 `analyze_single_review()` 실시간 분석으로 fallback한다.
- 기존 API 응답 구조는 유지한다.
- RTI 계산식과 점수 기준은 변경하지 않는다.
- 초기 적용 범위는 `/api/internal/ai/reviews/product-detail`로 제한한다.

## 3. 대상 테이블

이번 전략의 대상 테이블은 아래 두 개다.

- `reviews`
- `review_trust_scores`

`reviews`는 API 응답에 필요한 raw review 필드를 제공하고, `review_trust_scores`는 저장된 RTI score와 reasons를 제공한다.

## 4. 기본 흐름

```txt
product-detail 요청
-> reviews 테이블에서 raw reviews 조회
-> review_id 기준으로 review_trust_scores 조회
-> saved score가 있으면 saved score 사용
-> saved score가 없으면 analyze_single_review(review) 실행
-> AnalysisResult 리스트 생성
-> BatchResponse로 반환
```

구현 시에는 `review_id`를 기준으로 raw review와 saved score를 연결한다. saved score가 존재하는 review는 저장된 값을 `AnalysisResult` 형태로 변환하고, saved score가 없는 review만 기존 실시간 분석 함수를 실행한다.

## 5. 적용 우선순위

저장된 RTI score 재사용은 아래 순서로 확장한다.

1. `/api/internal/ai/reviews/product-detail`
2. `/api/internal/ai/products/product-list`
3. `/api/internal/ai/products/rti-trend`
4. `/api/internal/ai/products/risk-report`

v1-10의 첫 구현은 product-detail에만 적용한다. product-list, rti-trend, risk-report는 product-detail에서 lookup, mapper, fallback 동작이 안정화된 뒤 후속 커밋 또는 후속 버전에서 확장한다.

## 6. Fallback 전략

saved RTI score를 API에서 사용할 때는 저장 데이터 또는 DB 조회 문제가 있어도 기존 응답을 최대한 유지해야 한다.

- saved score 없음: 기존 `analyze_single_review(review)`를 실행한다.
- reasons JSON 파싱 실패: 빈 배열 `[]` 또는 안전한 기본값을 사용한다.
- DB 조회 실패: saved score 사용을 포기하고 기존 실시간 분석 흐름을 유지한다.
- 저장된 score와 raw review 필드가 함께 필요할 경우 raw review의 `content`, `user_id`, `review_date`를 유지한다.

즉, saved score lookup은 응답 성능을 개선하는 우선 경로이며, 장애가 발생해도 API 전체 실패로 이어지지 않게 한다.

## 7. Reasons 처리

AI 서버 내부 reasons 구조는 현재 형태를 유지한다.

```json
[
  {
    "code": "SHORT_REVIEW",
    "message": "리뷰 내용이 지나치게 짧음"
  }
]
```

`review_trust_scores.reasons`에는 JSON 문자열이 저장되어 있으므로 API 응답에 사용하기 전에 다시 `ReasonObject` 구조로 복원해야 한다.

- JSON 파싱 성공: 저장된 reasons를 `ReasonObject` 리스트로 변환한다.
- JSON 파싱 실패: 빈 배열 `[]` 또는 안전한 fallback을 사용한다.
- reasons 구조 자체는 변경하지 않는다.

## 8. 응답 구조 유지

현재 product-detail 응답의 review item은 `AnalysisResult` 기준이다. 저장된 score를 사용하더라도 기존 응답 구조를 유지해야 한다.

예상 구조는 아래와 같다.

```json
{
  "review_id": "123",
  "content": "리뷰 원문",
  "author": "user01",
  "date": "2026-05-01",
  "rti": 88,
  "level": "safe",
  "signals": {
    "text": 90,
    "behavior": 85,
    "network": 90
  },
  "input_features": {
    "image_count": 1,
    "quality_score": 0.5,
    "verified_purchase": "unknown",
    "repurchase": "unknown",
    "free_trial": "unknown",
    "reviews_written_today": 1,
    "similar_review_count": 0
  },
  "reasons": []
}
```

saved score를 사용하는 경우에도 `content`, `author`, `date`처럼 raw review에서 오는 필드는 유지한다. `rti`, `level`, `signals`, `input_features`, `reasons`는 저장된 score에서 복원 가능한 값을 우선 사용하되, 기존 `AnalysisResult` 응답 contract를 깨지 않는다.

## 9. 수정 금지 사항

v1-10 saved RTI API 연결 작업에서는 아래 항목을 변경하지 않는다.

- RTI 계산식 변경 금지
- signals 의미 변경 금지
- reasons 구조 변경 금지
- DB schema 변경 금지
- 서버 시작 시 DB reset/seed 자동 실행 금지
- Azure/MySQL 배포 구조 변경 금지

이번 문서 추가 커밋에서는 코드 수정도 하지 않는다. 특히 `main.py`, `ai/rti_score_repository.py`, RTI 계산 로직, DB 관련 실행 파일, `review_system.db`는 건드리지 않는다.

