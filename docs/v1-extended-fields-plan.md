# Re:view AI Server v1 Extended Fields Plan

## 1. 목적

v0에서는 기본 RTI 계산과 API 연동 구조를 우선 완성하기 위해 아래 확장 필드를 제외하였다.

- `key_signal`
- `patterns`
- `tags`
- `highlights`

v1에서는 실제 리뷰 데이터가 누적되고 RTI 결과 저장 구조가 정리된 이후, 위 확장 필드를 단계적으로 도입한다.

본 문서는 각 확장 필드의 의미, 필요한 입력 데이터, 구현 난이도, 도입 우선순위를 정리한다.

---

## 2. v0에서 제외한 이유

해당 필드들은 단순 RTI 점수 계산 결과에서 바로 산출되는 값이 아니다.

각 필드는 별도의 추가 분석 로직이 필요하다.

| 필드 | v0 제외 이유 |
|---|---|
| `tags` | `reasons`를 화면용 태그로 변환하는 별도 매핑 필요 |
| `key_signal` | 상품 단위로 `reasons.code`를 집계하는 로직 필요 |
| `highlights` | 리뷰 본문에서 의심 표현 구간을 추출하는 로직 필요 |
| `patterns` | 여러 리뷰를 묶어 시간/반복/유사도 패턴을 분석하는 로직 필요 |

---

## 3. 도입 우선순위

v1에서는 구현 난이도와 활용도를 기준으로 아래 순서로 도입한다.

| 우선순위 | 필드 | 난이도 | 설명 |
|---|---|---|---|
| 1 | `tags` | 낮음 | `reasons.message`를 화면용 태그로 변환 |
| 2 | `key_signal` | 낮음~중간 | 상품 단위 `reasons.code` 집계 |
| 3 | `highlights` | 중간 | 리뷰 본문 내 의심 표현 구간 추출 |
| 4 | `patterns` | 높음 | 상품 단위 이상 패턴 분석 |

---

## 4. tags

### 4.1 정의

`tags`는 리뷰 또는 샘플 리뷰에서 프론트엔드가 뱃지 형태로 보여줄 수 있는 화면용 문자열 배열이다.

v0에서는 별도 `tags` 필드를 두지 않고 `reasons(code/message)`를 그대로 사용하였다.

v1에서는 `reasons.message`를 기반으로 `tags`를 생성할 수 있다.

---

### 4.2 입력 데이터

필요한 입력 데이터:

- `reasons`
  - `code`
  - `message`

예시 입력:

```json
"reasons": [
  {
    "code": "REPETITIVE_KEYWORD",
    "message": "반복 표현 탐지"
  },
  {
    "code": "PURCHASE_UNKNOWN",
    "message": "구매 여부 확인 불가"
  }
]
```

---

### 4.3 출력 예시

```json
"tags": [
  "반복 표현 탐지",
  "구매 여부 확인 불가"
]
```

---

### 4.4 구현 방향

초기 구현은 단순 변환 방식으로 시작한다.

```txt
reasons[].message
→ tags[]
```

추후에는 프론트 표시용 문구를 별도 매핑할 수 있다.

예시:

| reason code | tag |
|---|---|
| `REPETITIVE_KEYWORD` | 반복 표현 |
| `SHORT_REVIEW` | 짧은 리뷰 |
| `EXCESSIVE_EXCLAMATION` | 과도한 강조 |
| `PURCHASE_UNKNOWN` | 구매확인 없음 |

---

## 5. key_signal

### 5.1 정의

`key_signal`은 상품 단위로 가장 많이 나타난 주요 의심 사유를 대표 신호로 표시하는 값이다.

예시:

```json
"key_signal": "반복 표현"
```

---

### 5.2 입력 데이터

필요한 입력 데이터:

- 상품에 속한 전체 리뷰의 `reasons`
- 각 reason의 `code`
- 각 reason의 `message`

---

### 5.3 산출 방식

상품에 속한 리뷰들의 `reasons.code`를 집계한다.

기본 흐름:

```txt
1. 상품의 전체 리뷰 분석 결과 조회
2. 모든 reasons.code 수집
3. 가장 많이 등장한 code 계산
4. 해당 code에 대응되는 message 또는 표시 문구를 key_signal로 반환
```

---

### 5.4 예시

입력:

```json
[
  {
    "review_id": "r001",
    "reasons": [
      { "code": "REPETITIVE_KEYWORD", "message": "반복 표현 탐지" }
    ]
  },
  {
    "review_id": "r002",
    "reasons": [
      { "code": "REPETITIVE_KEYWORD", "message": "반복 표현 탐지" }
    ]
  },
  {
    "review_id": "r003",
    "reasons": [
      { "code": "SHORT_REVIEW", "message": "리뷰 내용이 지나치게 짧음" }
    ]
  }
]
```

출력:

```json
"key_signal": "반복 표현 탐지"
```

---

### 5.5 고려사항

동률이 발생할 수 있다.

동률 처리 방식 후보:

- 가장 먼저 등장한 reason 사용
- 위험도가 높은 reason 우선
- 복수 key signal 반환

v1 초기에는 가장 많이 등장한 reason 1개만 반환하는 방식으로 시작한다.

---

## 6. highlights

### 6.1 정의

`highlights`는 리뷰 본문에서 의심 표현으로 판단된 구간을 분리하여 반환하는 배열이다.

프론트엔드는 이 값을 사용해 리뷰 본문 일부를 강조 표시할 수 있다.

---

### 6.2 입력 데이터

필요한 입력 데이터:

- `content`
- `reasons.code`
- 반복 키워드 목록
- 의심 표현 키워드 목록

---

### 6.3 출력 예시

```json
"highlights": [
  {
    "text": "이 제품 정말 최고예요. ",
    "is_highlighted": false,
    "highlight_type": null
  },
  {
    "text": "품질 완전 대박",
    "is_highlighted": true,
    "highlight_type": "danger"
  },
  {
    "text": ". 모든 분들께 강력추천드립니다.",
    "is_highlighted": false,
    "highlight_type": null
  }
]
```

---

### 6.4 구현 방향

v1 초기에는 rule-based 방식으로 시작한다.

기본 흐름:

```txt
1. content에서 의심 키워드 탐색
2. 탐지된 키워드 위치 계산
3. 원문을 일반 구간과 하이라이트 구간으로 분리
4. highlight_type 부여
```

초기 highlight 대상:

- 반복 키워드
- 과도한 홍보성 표현
- 과도한 느낌표
- 지나치게 짧은 리뷰

---

### 6.5 고려사항

`highlights`는 문자열 구간을 다루기 때문에 프론트 렌더링과 밀접하게 연결된다.

따라서 v1 초기에는 단순 키워드 기반으로 구현하고, 추후 모델 기반 구간 추출로 확장한다.

---

## 7. patterns

### 7.1 정의

`patterns`는 상품 단위로 여러 리뷰를 묶어 분석한 이상 패턴 목록이다.

예시:

```json
"patterns": [
  {
    "icon_type": "repeat",
    "title": "반복 표현 증가",
    "description": "짧고 유사한 표현이 일부 리뷰에 몰려 있습니다.",
    "stat_value": "18건",
    "status": "주의"
  }
]
```

---

### 7.2 입력 데이터

필요한 입력 데이터:

- 상품 단위 리뷰 목록
- `review_date`
- `rti`
- `level`
- `reasons`
- `content`
- `user_id`
- `similar_review_count`

---

### 7.3 후보 패턴

v1에서 검토할 패턴 후보는 아래와 같다.

| 패턴 | 설명 |
|---|---|
| 반복 표현 집중 | 특정 reason code가 상품 내 리뷰에서 많이 발생 |
| 짧은 리뷰 비율 증가 | `SHORT_REVIEW` 비율이 높음 |
| 위험 리뷰 비율 증가 | `danger` 또는 `warn` 리뷰 비율 증가 |
| 특정 날짜 리뷰 집중 | 특정 날짜에 리뷰가 몰림 |
| 유사 리뷰 증가 | `similar_review_count`가 높은 리뷰 증가 |

---

### 7.4 구현 방향

v1 초기에는 간단한 통계 기반으로 시작한다.

예시:

```txt
상품 전체 리뷰 중 REPETITIVE_KEYWORD 발생 리뷰 수 계산
→ 일정 기준 이상이면 patterns에 추가
```

---

### 7.5 시간대 패턴에 대한 제한

현재 데이터에는 `review_date`만 있으며, 시간 정보는 없다.

따라서 v1 초기에는 일자별 trend는 가능하지만, “새벽 1~3시 리뷰 집중” 같은 시간대 패턴은 계산할 수 없다.

시간대 패턴을 도입하려면 아래 필드가 필요하다.

- `review_datetime`
- 또는 시간 정보를 포함한 `created_at`

---

## 8. 필드별 도입 조건

| 필드 | v1 도입 조건 |
|---|---|
| `tags` | reasons 구조가 안정적으로 유지될 것 |
| `key_signal` | 상품 단위 RTI 결과 저장 또는 조회가 가능할 것 |
| `highlights` | content와 reason code 매핑 기준이 정리될 것 |
| `patterns` | 상품 단위 리뷰 수가 충분히 확보될 것 |

---

## 9. API 반영 방향

v1에서 필드를 도입할 때는 기존 v0 API 응답을 깨지 않도록 선택 필드로 추가한다.

예시:

```json
{
  "review_id": "r001",
  "rti": 72,
  "level": "warn",
  "reasons": [
    {
      "code": "REPETITIVE_KEYWORD",
      "message": "반복 표현 탐지"
    }
  ],
  "tags": [
    "반복 표현 탐지"
  ]
}
```

---

## 10. v1 우선 구현 후보

가장 먼저 구현할 후보는 아래 두 개이다.

1. `tags`
2. `key_signal`

이 두 필드는 기존 `reasons` 데이터만으로도 구현 가능하므로, 별도 모델 없이 rule-based 방식으로 시작할 수 있다.

`highlights`와 `patterns`는 추가 설계와 충분한 데이터가 필요하므로 후순위로 둔다.

---

## 11. 완료 기준

- 확장 필드별 정의 정리
- 필드별 입력 데이터 정리
- 필드별 출력 예시 정리
- 구현 난이도 및 우선순위 정리
- v1 초기 구현 후보 선정
- v0 API와의 호환 방식 정리

---

## 12. 결론

v1 확장 필드는 기존 RTI 결과와 `reasons(code/message)` 구조를 기반으로 단계적으로 도입한다.

초기에는 구현 난이도가 낮은 `tags`와 `key_signal`을 먼저 도입하고, 이후 `highlights`와 `patterns`를 추가 분석 로직으로 확장한다.

이를 통해 v1에서는 단순 RTI 점수 제공을 넘어, 프론트엔드에서 해석 가능한 분석 사유와 상품 단위 패턴 정보를 제공할 수 있도록 한다.