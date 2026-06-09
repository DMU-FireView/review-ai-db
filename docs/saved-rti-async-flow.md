# Saved RTI 비동기 분석 흐름

## 문서 목적

`saved RTI`는 이미 계산되어 DB에 저장된 리뷰 신뢰도 점수를 의미한다.

비동기 Job/Queue 구조가 도입되면 FastAPI Worker가 리뷰 분석을 완료한 뒤 RTI 결과를 `review_trust_scores`에 저장하고, 이후 같은 리뷰에 대한 요청에서는 RTI를 다시 계산하지 않고 저장된 결과를 재사용할 수 있다.

이 문서는 saved RTI가 비동기 분석 흐름에서 담당하는 역할과 실제 API 연결 전에 협의해야 할 항목을 정리한다.

## 1. saved RTI 정의

saved RTI는 리뷰에 대해 이미 계산되어 `review_trust_scores`에 저장된 RTI 결과다.

예상 저장 항목은 다음과 같다.

```text
review_id
rti
level
text_score
behavior_score
network_score
reasons
created_at
```

실제 저장 컬럼과 데이터 형식은 DB schema 및 분석 결과 모델을 기준으로 확인해야 한다.

## 2. saved RTI가 필요한 이유

saved RTI를 사용하는 이유는 다음과 같다.

```text
- 같은 리뷰를 반복 분석하지 않기 위함
- API 응답 속도 개선
- 분석 결과 재사용
- 비동기 Worker가 계산한 결과를 프론트 조회 API에서 사용 가능
- RTI 산출 결과를 DB에 남겨 디버깅/검증 가능
```

분석과 조회를 분리하면 Worker는 계산에 집중하고, 결과 조회 API는 저장된 값을 빠르게 읽어 응답할 수 있다.

## 3. 비동기 Job 흐름에서의 위치

saved RTI는 Worker의 RTI 분석 단계와 프론트 결과 조회 단계 사이에 위치한다.

```text
프론트 분석 요청
→ Spring이 product_analysis_job 생성
→ Redis Queue에 분석 작업 등록
→ FastAPI Worker가 크롤링 수행
→ reviews 테이블 저장
→ RTI 분석 수행
→ review_trust_scores에 saved RTI 저장
→ product_analysis_job 상태 DONE
→ 프론트가 결과 조회
→ API가 saved RTI를 읽어 응답
```

Job을 `DONE`으로 변경하는 시점에는 필요한 리뷰의 RTI 저장이 정상적으로 완료되었는지 확인해야 한다.

## 4. saved RTI 저장 시점

FastAPI Worker가 리뷰별 RTI 분석을 완료한 직후 saved RTI를 저장하는 방식을 후보로 제안한다.

```text
review input
→ RTI analysis
→ rti / level / signals / reasons 생성
→ review_trust_scores 저장
```

저장이 실패한 경우 전체 Job을 실패로 처리할지, 일부 리뷰만 실패 상태로 기록할지에 대한 기준은 별도 협의가 필요하다.

## 5. saved RTI 조회 시점

saved RTI는 다음 조회 및 계산 과정에서 사용할 수 있다.

```text
- product-detail 결과 조회 시 saved RTI 사용
- product-list 요약 조회 시 saved RTI 사용
- risk-report 생성 시 saved RTI 사용
- trend 계산 시 saved RTI 사용
```

다만 실제 endpoint 연결은 Job/Queue/Worker 구조와 결과 조회 주체가 확정된 후 진행해야 한다.

## 6. 기존 실시간 분석과의 관계

현재 FastAPI에는 요청을 받으면 즉시 RTI를 계산하는 실시간 분석 흐름이 있다.

saved RTI를 조회 API에 연결하면 다음과 같이 분석과 조회를 분리할 수 있다.

```text
기존:
API 요청 → 즉시 RTI 분석 → 응답

saved RTI 기반:
API 요청 → DB에 저장된 RTI 조회 → 응답
```

saved RTI가 없을 때 실시간 분석 fallback을 수행할지, 비동기 Job 분석 완료 후에만 조회를 허용할지는 팀 협의가 필요하다.

## 7. fallback 정책 협의

saved RTI가 없는 경우 다음 정책을 후보로 검토할 수 있다.

```text
A안: 실시간 분석 fallback 수행
B안: 아직 분석 전 상태로 보고 빈 결과/대기 응답 반환
C안: Job을 새로 생성하여 비동기 분석 요청
```

AI 파트 기준으로 초기에는 기존 실시간 흐름을 활용할 수 있는 A안 또는 명확하게 분석 상태를 구분하는 B안을 검토할 수 있다.

다만 fallback 선택은 API 응답 계약과 Job 생성 주체에 영향을 주므로 실제 API 동작 변경은 팀 협의 후 진행해야 한다.

## 8. saved RTI와 review_id

saved RTI는 `review_id`를 기준으로 `reviews`의 원본 리뷰와 연결된다.

안정적인 저장과 재사용을 위해 다음 항목을 협의해야 한다.

```text
- review_id가 플랫폼별로 안정적인지
- 같은 리뷰가 다시 수집될 때 동일 review_id를 유지할 수 있는지
- 중복 저장 시 skip할지 update할지
- product_id + review_id 복합 기준이 필요한지
```

플랫폼 간 `review_id` 충돌 가능성이 있다면 `mall`, `product_id` 또는 내부 리뷰 식별자를 함께 사용하는 방안도 검토해야 한다.

## 9. saved RTI API 연결 보류 이유

다음 항목이 확정되지 않았으므로 saved RTI의 실제 API 연결은 보류한다.

```text
- product_analysis_job 흐름이 아직 확정되지 않음
- Redis Queue 메시지 구조가 아직 확정되지 않음
- FastAPI Worker 책임 범위가 아직 확정되지 않음
- 프론트가 결과를 조회하는 방식이 아직 확정되지 않음
- Spring과 FastAPI 중 누가 최종 결과 API를 담당할지 정해야 함
```

API를 먼저 연결하면 이후 비동기 구조 합의에 따라 응답 형식과 endpoint 책임을 다시 변경해야 할 수 있다.

## 10. AI 파트에서 지금 할 수 있는 준비 작업

비동기 구조 협의 전에도 다음 준비 작업을 진행할 수 있다.

```text
- saved RTI 개념 정리
- review_trust_scores 저장/조회 흐름 문서화
- fallback 정책 후보 정리
- API 연결 전 확인해야 할 항목 정리
- mapper/helper 함수는 endpoint 연결 전까지 독립적으로 유지
```

준비 작업은 실제 endpoint 동작을 변경하지 않고, 이후 책임 범위가 확정되었을 때 재사용할 수 있는 단위로 유지한다.

## 11. 결론

saved RTI는 비동기 분석 구조에서 계산 결과를 재사용하고 조회 API의 응답 속도를 개선하는 데 중요한 역할을 한다. 또한 분석 결과를 DB에 보존하여 검증과 디버깅이 가능하게 한다.

다만 실제 API 연결은 Job, Redis Queue, FastAPI Worker 책임 범위 및 프론트 결과 조회 방식이 합의된 뒤 진행하는 것이 안전하다.

이 문서는 협의를 위한 흐름 문서이며 실제 API, DB schema, Redis/Worker 또는 크롤러 코드를 변경하지 않는다.
