# FastAPI Worker 책임 범위 초안

## 문서 목적

비동기 분석 구조에서 FastAPI는 단순 API 서버뿐 아니라 Redis Queue에서 작업을 꺼내 처리하는 Worker 역할을 맡을 수 있다.

다만 FastAPI Worker가 크롤링, 데이터 저장, RTI 분석, 작업 상태 관리 중 어디까지 담당할지는 아직 팀 합의가 필요하다. 이 문서는 FastAPI Worker가 맡을 수 있는 책임 범위를 정리하고 협의가 필요한 항목을 명확히 하기 위한 초안이다.

## 1. 현재 제안된 비동기 흐름

현재 제안된 전체 분석 흐름은 다음과 같다.

```text
프론트 요청
→ Spring이 product_analysis_job 생성
→ Spring이 Redis Queue에 작업 등록
→ FastAPI Worker가 Redis Queue에서 작업 수신
→ 크롤링 / RTI 분석 / 결과 저장
→ product_analysis_job 상태 업데이트
```

Spring은 분석 요청 접수와 Job 생성을 담당하고, FastAPI Worker는 Queue에 등록된 작업을 비동기로 처리하는 구조를 전제로 한다.

## 2. FastAPI Worker 후보 역할

FastAPI Worker가 맡을 수 있는 역할 후보는 다음과 같다.

```text
1. Redis Queue consume
2. Queue 메시지 검증
3. product_analysis_job 상태 RUNNING 업데이트
4. productUrl 기준 크롤링
5. raw JSON 저장
6. 리뷰 정규화
7. reviews 테이블 insert
8. RTI 분석
9. review_trust_scores 저장
10. product_analysis_job 상태 DONE 또는 FAILED 업데이트
```

위 역할 전체를 FastAPI가 담당해야 한다는 의미는 아니며, 실제 책임 범위는 팀 협의를 통해 결정한다.

## 3. 역할별 설명

| 역할 | 설명 |
| --- | --- |
| Redis Queue consume | Spring이 등록한 분석 작업을 Worker가 수신한다. |
| Queue 메시지 검증 | `jobId`, `mall`, `productId`, `productUrl` 등 필수값과 메시지 형식을 확인한다. |
| Job 상태 `RUNNING` 업데이트 | 작업이 실제로 시작되었음을 Spring과 프론트가 확인할 수 있도록 상태를 반영한다. |
| 크롤링 | `productUrl`을 기준으로 상품 리뷰 원천 데이터를 수집한다. |
| raw JSON 저장 | 수집한 원본 데이터를 보존하여 변환 실패 조사, 재처리 및 디버깅에 활용한다. |
| 리뷰 정규화 | 쇼핑몰별로 다른 원천 데이터를 공통 리뷰 형식으로 변환한다. |
| `reviews` 테이블 insert | 정규화된 리뷰를 이후 분석과 조회에 사용할 수 있도록 DB에 저장한다. |
| RTI 분석 | 기존 분석 로직을 사용해 `rti`, `level`, `signals`, `reasons`를 생성한다. |
| `review_trust_scores` 저장 | 생성된 RTI 결과를 saved RTI로 재사용할 수 있도록 DB에 저장한다. |
| Job 상태 `DONE` 또는 `FAILED` 업데이트 | 프론트와 Spring이 작업 완료 또는 실패 상태를 확인할 수 있도록 최종 상태를 반영한다. |

## 4. 책임 범위 선택지

### A안: FastAPI가 전체 처리 담당

```text
Queue consume
→ 크롤링
→ DB insert
→ RTI 분석
→ RTI 저장
→ Job 상태 업데이트
```

장점:

```text
- AI/크롤링/분석 흐름을 한 곳에서 처리 가능
- Spring은 Job 생성과 상태 조회에 집중 가능
```

단점:

```text
- FastAPI 책임이 커짐
- DB write 범위가 넓어짐
- Worker 장애 시 처리 복잡도 증가
```

### B안: FastAPI는 분석만 담당

```text
Spring 또는 별도 크롤러
→ 리뷰 DB 저장
→ FastAPI는 RTI 분석 및 score 저장만 담당
```

장점:

```text
- FastAPI 책임이 줄어듦
- 백엔드가 데이터 저장 흐름을 통제하기 쉬움
```

단점:

```text
- 크롤러/저장/분석이 분리되어 연동 API가 더 필요할 수 있음
```

### C안: 단계적 적용

```text
1단계: FastAPI가 RTI 분석/저장만 담당
2단계: 크롤러 MVP 연결
3단계: Queue Worker 통합
```

AI 파트 기준으로는 **C안: 단계적 적용**을 추천한다. 기존 RTI 분석 및 저장 흐름을 먼저 안정적으로 연결한 뒤 크롤러와 Queue를 순차적으로 통합하면 각 단계의 책임과 장애 원인을 구분하기 쉽다.

## 5. AI 파트 추천 방향

초기부터 전체 Worker를 한 번에 구현하면 Queue 처리, 크롤링, DB 저장, 분석 및 상태 관리가 동시에 결합된다. 협의되지 않은 책임과 장애 처리 방식이 구현에 먼저 반영될 수 있으므로 단계적으로 진행하는 것이 안전하다.

추천 단계는 다음과 같다.

```text
1. Queue 메시지 구조 확정
2. Job 상태값 확정
3. Worker 책임 범위 확정
4. RTI 분석/저장 흐름부터 연결
5. Crawler MVP 연결
6. 전체 Queue Worker로 확장
```

## 6. 기존 v1 파이프라인과의 연결

현재 v1 파이프라인은 다음 흐름으로 준비되어 있다.

```text
raw JSON
→ converter
→ DB insert
→ RTI score 저장
→ saved RTI lookup
```

FastAPI Worker가 크롤링까지 담당한다면 기존 파이프라인 앞에 Queue와 crawler 단계를 연결할 수 있다.

```text
Queue job
→ crawler
→ raw JSON
→ converter
→ reviews insert
→ RTI 분석
→ review_trust_scores 저장
→ job DONE
```

이 경우 기존 converter, DB insert, RTI score 저장 및 saved RTI 흐름을 재사용할 수 있는지 확인하고, Worker에서 각 단계를 호출하는 방식과 실패 경계를 별도로 정의해야 한다.

## 7. 협의 필요 항목

아래 항목은 실제 Worker 구현 전에 Spring과 FastAPI 담당자 간 협의가 필요하다.

```text
- FastAPI가 크롤링까지 맡을지
- FastAPI가 reviews DB insert까지 맡을지
- FastAPI가 product_analysis_job을 직접 업데이트할지
- FastAPI가 Spring API를 통해 상태를 업데이트할지
- Worker 실패 시 재시도 정책을 둘지
- 기존 실시간 API와 Worker를 어떻게 분리할지
```

## 8. 협의 전 보류할 개발

아래 개발은 책임 범위와 연동 방식에 대한 팀 합의 전까지 보류한다.

```text
- Redis Queue consume 코드
- 실제 Worker loop 구현
- product_analysis_job 상태 업데이트 코드
- 크롤러 실제 구현
- main.py endpoint 동작 변경
- saved RTI API 실제 연결
```

## 9. 결론

FastAPI Worker는 비동기 분석 구조의 핵심 역할을 할 수 있지만, 크롤링부터 DB 저장과 상태 관리까지 담당하면 책임 범위가 크게 넓어진다.

따라서 Queue 메시지와 Job 상태, Worker 책임 범위를 먼저 합의하고, RTI 분석 및 저장부터 크롤러 MVP와 Queue Worker 순서로 단계적으로 구현하는 것이 안전하다.

이 문서는 협의를 위한 초안이며 실제 API, DB schema, Redis/Worker 또는 크롤러 동작을 변경하지 않는다.
