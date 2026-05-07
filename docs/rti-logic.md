# RTI 계산 로직 문서

## 1. RTI란?

RTI는 Review Trust Index의 약자로, 리뷰의 신뢰도를 0점부터 100점까지 수치화한 점수입니다.

점수가 높을수록 신뢰 가능한 리뷰로 판단하고, 점수가 낮을수록 가짜 리뷰 또는 조작 리뷰 가능성이 높다고 판단합니다.

현재 v0에서는 실제 AI 모델이 아니라 규칙 기반 mock scoring 방식을 사용합니다.

## 2. v0 기준 입력 데이터

RTI 계산은 원본 크롤링 데이터를 직접 사용하지 않고, 정규화된 공통 리뷰 데이터를 기준으로 수행합니다.

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

## 3. v0 기준 분석 신호

v0에서는 다음 3가지 신호를 사용합니다.

| 신호 | 설명 |
|---|---|
| Text Score | 리뷰 본문 표현 및 품질 분석 |
| Behavior Score | 구매/작성/첨부 정보 기반 행동 신호 분석 |
| Network Score | 유사 리뷰 및 반복 패턴 분석 |

## 4. Text Score

리뷰 본문과 품질 정보를 분석하여 점수를 계산합니다.

기본 점수는 100점이며, 조건에 따라 감점합니다.

| 조건 | 감점 기준 |
|---|---|
| 홍보성 표현 반복 | 동일 키워드가 2회 이상 반복되면 감점 |
| 리뷰 길이 부족 | 리뷰 내용이 지나치게 짧으면 감점 |
| 과도한 느낌표 | 느낌표가 3개 이상이면 감점 |
| 낮은 품질 점수 | `quality_score`가 0.1 미만이면 감점 |

반복 탐지 대상 키워드 예시:

```txt
최고, 대박, 강력추천, 완전, 무조건, 좋아요, 만족
```

예시 감점 사유:

- 반복 표현 탐지: '대박' 2회
- 반복 표현 탐지: '만족' 2회
- 리뷰 내용이 지나치게 짧음
- 과도한 느낌표 사용
- 리뷰 품질 점수 낮음

## 5. Behavior Score

리뷰 작성 및 구매 관련 신호를 분석하여 점수를 계산합니다.

기본 점수는 100점이며, 조건에 따라 감점 또는 가점을 적용합니다.

| 조건 | 처리 방식 |
|---|---|
| 구매 여부 확인 불가 | `verified_purchase`가 `unknown`이면 감점 |
| 구매 이력 미확인 | `verified_purchase`가 `false`이면 감점 |
| 체험단/무상 제공 가능성 | `free_trial`이 `true`이면 감점 |
| 같은 날짜 다수 리뷰 작성 | `reviews_written_today`가 3 이상이면 감점 |
| 이미지 첨부 없음 | `image_count`가 0이면 감점 |
| 재구매 리뷰 신호 | `repurchase`가 `true`이면 소폭 가점 |

현재 네이버 원본 데이터에서는 계정 생성일을 직접 확인하기 어렵기 때문에 `account_age_days`는 v0에서 `null`로 처리합니다.

예시 판단 사유:

- 구매 여부 확인 불가
- 구매 이력 미확인
- 체험단/무상 제공 리뷰 가능성
- 동일 작성자의 같은 날짜 다수 리뷰 작성
- 이미지 첨부 없음
- 재구매 리뷰 신호

## 6. Network Score

유사 리뷰 개수와 반복 패턴을 기반으로 점수를 계산합니다.

기본 점수는 100점이며, `similar_review_count` 값에 따라 감점합니다.

| 조건 | 설명 |
|---|---|
| 유사 리뷰 1개 이상 | 일부 유사 리뷰 패턴 탐지 |
| 유사 리뷰 5개 이상 | 유사 리뷰 네트워크 군집 탐지 |

현재 v0에서는 완전한 AI 유사도 모델이 아니라, 리뷰 본문을 기반으로 한 단순 유사도 계산을 사용합니다.

예시 감점 사유:

- 일부 유사 리뷰 패턴 탐지
- 유사 리뷰 네트워크 군집 탐지

## 7. RTI 계산 공식

v0에서는 다음 가중치를 사용합니다.

```txt
RTI = Text Score * 0.4 + Behavior Score * 0.35 + Network Score * 0.25
```

가중치 의미:

| 항목 | 가중치 |
|---|---|
| Text Score | 40% |
| Behavior Score | 35% |
| Network Score | 25% |

## 8. 등급 기준

| 조건 | 등급 | 의미 |
|---|---|---|
| RTI 80 이상, 주요 감점 사유 없음 | safe | 신뢰 가능 |
| RTI 50 이상 또는 감점 사유 존재 | warn | 의심 필요 |
| RTI 50 미만 | danger | 위험 리뷰 가능성 높음 |

단, `재구매 리뷰 신호`는 긍정 신호이므로 주요 감점 사유로 보지 않습니다.

## 9. 출력 예시

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
  "level": "warn",
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

## 10. 현재 모듈화 구조

RTI 계산 코드는 현재 다음과 같이 모듈화되어 있습니다.

```txt
ai/text_analyzer.py
ai/behavior_analyzer.py
ai/network_analyzer.py
ai/rti_scoring.py
```

각 파일의 역할은 다음과 같습니다.

| 파일명 | 역할 |
|---|---|
| `text_analyzer.py` | 리뷰 본문 표현, 길이, 느낌표, 품질 점수 기반 Text Score 계산 |
| `behavior_analyzer.py` | 구매 여부, 체험단 여부, 이미지 첨부, 같은 날짜 작성 수 기반 Behavior Score 계산 |
| `network_analyzer.py` | 유사 리뷰 개수 기반 Network Score 계산 |
| `rti_scoring.py` | 세 분석 점수를 통합하여 최종 RTI와 level 산출 |

현재 `rti_scoring.py`는 개별 분석 로직을 직접 가지고 있지 않고, 각 analyzer 모듈에서 점수를 받아 최종 RTI만 계산합니다.

## 11. Cloud Natural Language API 연결 준비 구조

Text Score 계산에는 Google Cloud Natural Language API 감성 분석 결과를 보조 신호로 추가할 예정입니다.

현재는 실제 API 호출이 아니라, 연결 준비용 구조만 추가된 상태입니다.

추가된 파일은 다음과 같습니다.

```txt
ai/sentiment_client.py
```

현재 구조는 다음과 같습니다.

```txt
ai/text_analyzer.py
        ↓
ai/sentiment_client.py
        ↓
Google Cloud Natural Language API
```

현재 `sentiment_client.py`는 기본적으로 mock/fallback 모드로 동작합니다.

즉, API 키나 Google Cloud 인증 정보가 없어도 로컬에서 RTI 계산이 정상적으로 실행됩니다.

현재 기본 상태:

```txt
ENABLE_CLOUD_NLP=false
```

이 경우 실제 Google Cloud Natural Language API는 호출되지 않고, neutral mock 결과를 반환합니다.

추후 실제 API 연결 시에는 다음 작업이 필요합니다.

- Google Cloud 프로젝트 생성 또는 확인
- Cloud Natural Language API 활성화
- 서비스 계정 키 발급
- 로컬 환경변수 설정
- `ENABLE_CLOUD_NLP=true` 설정
- 실제 sentiment score / magnitude를 Text Score 계산에 반영

현재 v0에서는 API 호출 없이 규칙 기반 mock scoring + sentiment fallback 구조로 동작합니다.
