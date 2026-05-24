# Re:view AI Server v1 RTI Persistence Plan

## 1. 목적

v1에서는 리뷰 분석 결과를 매번 실시간으로 계산할지, 또는 DB에 저장한 뒤 재사용할지 결정해야 한다.

v0에서는 API 요청이 들어올 때마다 리뷰 데이터를 조회하고 RTI를 실시간으로 계산했다.

v1에서는 실제 리뷰 데이터가 누적될 예정이므로, 분석 결과를 `review_trust_scores` 테이블에 저장하는 방식을 검토한다.

---

## 2. 현재 v0 방식

현재 v0 흐름은 아래와 같다.

```txt
TriggerRequest 수신
→ product_id / url 기준 리뷰 조회
→ text / behavior / network 분석
→ RTI 계산
→ API 응답 반환
```

이 방식은 테스트와 데모에는 적합하다.

하지만 리뷰 데이터가 많아지면 같은 리뷰를 반복해서 분석할 수 있고, API 응답 속도가 느려질 수 있다.

---

## 3. v1에서 검토할 방식

v1에서는 두 가지 방식을 비교한다.

| 방식 | 설명 |
|---|---|
| 실시간 계산 방식 | API 요청 시마다 analyzer를 실행하여 RTI 계산 |
| 저장 후 조회 방식 | 리뷰별 RTI를 한 번 계산한 뒤 DB에 저장하고 재사용 |

---

## 4. 실시간 계산 방식

### 장점

- 구현이 단순하다.
- 최신 analyzer 로직이 항상 바로 반영된다.
- 별도 저장/갱신 정책이 필요 없다.

### 단점

- 같은 리뷰를 반복 계산할 수 있다.
- 리뷰 수가 많아지면 API 응답이 느려질 수 있다.
- 분석 이력을 추적하기 어렵다.

---

## 5. 저장 후 조회 방식

### 장점

- 한 번 계산한 RTI 결과를 재사용할 수 있다.
- API 응답 속도를 개선할 수 있다.
- 분석 이력을 DB에 남길 수 있다.
- 추후 대시보드, 통계, 모델 고도화에 활용할 수 있다.

### 단점

- analyzer 로직이 바뀌면 기존 결과를 재계산해야 한다.
- 저장/갱신 정책이 필요하다.
- DB insert/update 로직이 추가로 필요하다.

---

## 6. review_trust_scores 테이블 활용

v1에서는 `review_trust_scores` 테이블을 RTI 결과 저장 후보 테이블로 사용한다.

저장 후보 필드는 아래와 같다.

| 필드명 | 설명 |
|---|---|
| `score_id` | RTI 결과 고유 ID |
| `review_id` | 분석 대상 리뷰 ID |
| `rti` | 최종 RTI 점수 |
| `level` | safe / warn / danger |
| `text_score` | 텍스트 신뢰 점수 |
| `behavior_score` | 행동 신뢰 점수 |
| `network_score` | 네트워크 신뢰 점수 |
| `reasons` | code/message 구조의 판단 사유 |
| `created_at` | 분석 결과 생성 시각 |

---

## 7. 저장 기준

v1에서는 리뷰 단위로 RTI 결과를 저장하는 방향을 우선 검토한다.

기본 기준은 아래와 같다.

```txt
reviews.review_id
→ review_trust_scores.review_id
```

즉, 하나의 리뷰에 대해 하나의 최신 RTI 결과를 저장하는 구조를 기본으로 한다.

---

## 8. 중복 저장 방지

RTI 결과 저장 시 `review_id` 기준으로 중복을 방지해야 한다.

기본 흐름은 아래와 같다.

```txt
1. review_id 기준 기존 RTI 결과 조회
2. 저장된 결과가 없으면 insert
3. 저장된 결과가 있으면 update 또는 skip
```

v1 초기에는 아래 방식 중 하나를 선택한다.

| 방식 | 설명 |
|---|---|
| skip | 이미 분석 결과가 있으면 재계산하지 않음 |
| update | analyzer를 다시 실행하고 기존 결과를 갱신 |
| versioning | 분석 결과를 이력으로 누적 저장 |

v1 초기에는 구현 난이도를 고려하여 `skip` 또는 `update` 방식을 우선 검토한다.

---

## 9. analyzer 변경 시 재계산 기준

RTI 계산 로직이나 analyzer가 변경되면 기존 저장 결과가 최신 기준과 달라질 수 있다.

따라서 v1 이후에는 재계산 기준이 필요하다.

검토할 기준:

- analyzer 코드가 변경된 경우
- reason code 정책이 변경된 경우
- scoring weight가 변경된 경우
- 입력 데이터가 수정된 경우
- 일정 기간이 지난 경우

---

## 10. API 응답과 저장 결과 관계

v1에서는 API 응답을 만들 때 아래 두 가지 방식을 검토한다.

### 10.1 실시간 계산 후 응답

```txt
리뷰 조회
→ analyzer 실행
→ RTI 계산
→ API 응답
```

### 10.2 저장 결과 조회 후 응답

```txt
리뷰 조회
→ review_trust_scores 조회
→ 저장 결과가 있으면 사용
→ 없으면 analyzer 실행 후 저장
→ API 응답
```

v1에서는 두 번째 방식이 장기적으로 더 적합하다.

---

## 11. 추천 v1 흐름

v1 초기 추천 흐름은 아래와 같다.

```txt
1. product_id / url 기준 리뷰 조회
2. 각 review_id에 대해 저장된 RTI 결과 확인
3. 저장 결과가 있으면 재사용
4. 저장 결과가 없으면 analyzer 실행
5. 계산된 RTI 결과를 review_trust_scores에 저장
6. API 응답 생성
```

---

## 12. reasons 저장 방식

`reasons`는 code/message 객체 배열이므로 DB 저장 시 JSON 문자열 형태로 저장할 수 있다.

예시:

```json
[
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

SQLite에서는 TEXT 컬럼에 JSON 문자열로 저장하고, API 응답 시 다시 JSON으로 변환하는 방식을 사용할 수 있다.

---

## 13. v1 확장 필드와의 관계

v1에서 도입할 확장 필드는 RTI 저장 결과를 기반으로 만들 수 있다.

| 확장 필드 | RTI 저장 결과 활용 방식 |
|---|---|
| `tags` | reasons.message를 화면용 태그로 변환 |
| `key_signal` | 상품 단위 reasons.code를 집계하여 대표 사유 선정 |
| `highlights` | reasons.code와 content를 기반으로 의심 구간 추출 |
| `patterns` | 여러 리뷰의 level, reasons, review_date를 상품 단위로 분석 |

따라서 RTI 결과 저장 구조는 v1 확장 기능의 기반이 된다.

---

## 14. v1 우선순위

### 1단계

- `review_trust_scores` 저장 후보 필드 확정
- reasons JSON 저장 방식 검토

### 2단계

- review_id 기준 저장 결과 조회 로직 설계
- 저장 결과가 없을 때 analyzer 실행 방식 설계

### 3단계

- insert/update 정책 결정
- analyzer 변경 시 재계산 기준 정리

### 4단계

- 저장된 RTI 결과 기반 API 응답 생성 방식 검토

---

## 15. 완료 기준

- RTI 결과 저장 필요성 정리
- 실시간 계산 방식과 저장 후 조회 방식 비교
- `review_trust_scores` 저장 후보 필드 정리
- review_id 기준 중복 저장 방지 기준 정리
- reasons JSON 저장 방식 정리
- v1 확장 필드와의 관계 정리

---

## 16. 결론

v1에서는 실제 리뷰 데이터가 누적될 예정이므로, RTI 결과를 매번 실시간 계산하는 방식만으로는 한계가 있다.

따라서 `review_trust_scores` 테이블을 활용해 리뷰별 RTI 결과를 저장하고, API 응답 시 저장 결과를 재사용하는 구조를 검토한다.

이 구조는 API 응답 속도 개선뿐 아니라, 이후 `tags`, `key_signal`, `highlights`, `patterns` 같은 확장 분석 기능의 기반이 된다.