# NAVER Worker 로컬 시뮬레이션 결과

## 문서 목적

이 문서는 실제 Redis Queue Worker를 구현하기 전에 로컬에서 검증한 NAVER 크롤링, RTI 분석, job summary 저장 흐름을 정리한다. 이후 FastAPI Worker 구현 시 참고할 입력 메시지, 단계별 책임, 성공 및 실패 상태 기준도 함께 기록한다.

현재 범위는 로컬 시뮬레이션이며 Redis, DB, Spring 또는 FastAPI endpoint와 연결하지 않는다.

## 1. 현재 검증 완료 흐름

현재 NAVER 상품 URL 1개를 기준으로 다음 흐름까지 로컬에서 검증했다.

```text
NAVER productUrl 입력
→ Playwright 크롤러 실행
→ 리뷰 관련 API body 캡처
→ JSON 내부 리뷰 배열 탐색
→ raw review schema로 매핑
→ raw JSON 저장
→ RTI 분석 스크립트 실행
→ RTI 결과 JSON 저장
→ local worker job summary 저장
```

검증 결과는 다음과 같다.

- 상품 URL 1개 기준으로 흐름을 실행했다.
- 리뷰 30개가 포함된 raw JSON 저장을 확인했다.
- 기존 text/behavior/network 기반 RTI 분석 로직으로 리뷰 30개 분석을 확인했다.
- RTI 결과의 `skipped_count`가 0개임을 확인했다.
- `output/naver_worker_job_<product_id>.json` 생성을 확인했다.

검증에 사용된 상품 ID는 `7195971829`이며, 생성된 job summary는 `status: DONE`, `review_count: 30`, `analyzed_count: 30`을 기록했다.

## 2. 로컬 시뮬레이션 스크립트

로컬 Worker 흐름 검증에는 다음 스크립트를 사용한다.

```text
scripts/simulate_naver_worker_job.py
```

스크립트의 역할은 다음과 같다.

- 실제 Redis Worker 구현 전 로컬 검증에 사용한다.
- `productUrl`을 입력받아 Playwright 크롤러와 RTI 분석 스크립트를 순서대로 실행한다.
- 크롤러가 생성한 raw JSON과 RTI 결과 JSON의 존재 여부, JSON 형식 및 처리 건수를 검증한다.
- 최종 결과를 local worker job summary JSON으로 저장한다.
- Redis, DB, Spring 및 FastAPI endpoint와 연결하지 않는다.

headed 모드 실행 예시는 다음과 같다.

```powershell
python scripts/simulate_naver_worker_job.py "https://brand.naver.com/hera/products/7195971829" --headed
```

`--headed`를 생략하면 Playwright 크롤러는 기본 headless 모드로 실행된다.

## 3. 입력 메시지 계약 초안

실제 Redis Queue Worker로 전환할 때 예상되는 입력 메시지 예시는 다음과 같다.

```json
{
  "jobId": "local-7195971829",
  "platform": "NAVER",
  "productId": "7195971829",
  "productUrl": "https://brand.naver.com/hera/products/7195971829"
}
```

| 필드 | 설명 |
| --- | --- |
| `jobId` | `product_analysis_job` 상태 업데이트 기준 |
| `platform` | NAVER 등 크롤링 대상 플랫폼 구분 |
| `productId` | 플랫폼 내 상품 식별자 |
| `productUrl` | 크롤링 대상 상품 URL |

이 구조는 Queue message 계약 초안이며 실제 필드명, 필수 여부 및 직렬화 형식은 구현 전에 최종 확인해야 한다.

## 4. Worker 단계별 책임 초안

실제 Queue Worker의 예상 처리 순서는 다음과 같다.

1. Queue message 수신
2. `product_analysis_job` 상태를 `RUNNING`으로 처리
3. `productUrl` 기준 크롤링
4. raw reviews 생성
5. `review_id` 기준 신규 리뷰 판별
6. 신규 리뷰만 `reviews` insert
7. 신규 리뷰만 RTI 분석
8. 신규 리뷰만 `review_trust_scores` insert
9. `product_analysis_job` 상태를 `DONE` 또는 `FAILED`로 처리

현재 로컬 시뮬레이션에서는 크롤링, raw JSON 검증, RTI 분석 및 job summary 저장만 수행했다. `reviews`와 `review_trust_scores` DB insert, `product_analysis_job` 상태 업데이트는 수행하지 않았다.

## 5. DONE 조건

로컬 시뮬레이션의 기본 `DONE` 조건은 다음과 같다.

- `productUrl`이 유효하고 `product_id`를 추출할 수 있다.
- 이번 크롤링의 raw JSON 또는 유효한 기존 fallback raw JSON을 사용할 수 있다.
- 사용할 raw JSON에 `reviews` 배열이 존재하고 리뷰가 1개 이상이다.
- RTI 분석 결과 JSON이 생성된다.
- RTI 결과의 `analyzed_count`가 1개 이상이다.
- local worker job summary JSON 저장이 완료된다.

정상 크롤링 결과를 사용하면 crawl step은 `DONE`, 기존 성공 raw JSON을 fallback으로 사용하면 `FALLBACK_USED`로 기록된다. 두 경우 모두 RTI 분석과 summary 저장이 성공하면 최종 job status는 `DONE`이 될 수 있다.

## 6. FAILED 조건

다음 조건에서는 local worker job을 `FAILED`로 처리한다.

- `productUrl`이 누락되거나 `product_id` 추출에 실패한다.
- 크롤러가 실패하고 사용할 수 있는 fallback raw JSON도 없다.
- raw JSON 파일이 없고 유효한 fallback도 없다.
- raw JSON에 `reviews` 배열이 없다.
- raw JSON의 리뷰 수가 0개이고 유효한 fallback도 없다.
- RTI 분석 스크립트 실행에 실패한다.
- RTI 결과 JSON 파일이 없거나 JSON 파싱에 실패한다.
- RTI 결과의 `analyzed_count`가 0개이거나 유효한 정수가 아니다.
- job summary를 포함한 결과 JSON 저장에 실패한다.

크롤러 실행 실패나 이번 실행의 리뷰 0개만으로 즉시 `FAILED`가 되는 것은 아니다. 해당 상황에서는 먼저 fallback 정책을 적용하고, 유효한 fallback도 없을 때 최종 실패로 처리한다.

## 7. fallback 정책

로컬 시뮬레이션에는 일시적인 크롤링 실패가 전체 RTI 흐름 검증을 막지 않도록 다음 fallback 정책을 적용했다.

- 크롤러가 일시적으로 실패하거나 이번 실행에서 리뷰 0개가 나온 경우 fallback을 확인한다.
- `data/raw/naver_reviews_<product_id>_playwright.json`에 기존 성공 결과가 있고 `reviews`가 1개 이상이면 해당 파일을 사용한다.
- fallback 사용 시 job summary의 crawl step status를 `FALLBACK_USED`로 기록한다.
- job summary 최상위에 `used_fallback_raw_json: true`를 기록한다.
- 정상 크롤링 결과를 사용하면 `used_fallback_raw_json: false`를 기록한다.
- fallback 파일도 없거나 유효한 리뷰가 없으면 `FAILED`로 처리한다.

fallback은 로컬 Worker 흐름을 계속 검증하기 위한 정책이다. 실제 운영 Worker에서 fallback을 허용할지, 데이터 최신성을 어떻게 보장할지는 별도 협의가 필요하다.

## 8. review_id 기준 중복 저장 정책

MVP의 중복 저장 여부는 상품 단위가 아니라 개별 `review_id` 단위로 판단한다.

- 상품에 기존 리뷰가 있다는 이유로 크롤링 결과 전체를 skip하지 않는다.
- DB에 없는 `review_id`만 신규 리뷰로 판단하여 `reviews`에 insert한다.
- 신규 `review_id`만 RTI 분석 후 `review_trust_scores`에 저장한다.
- 이미 존재하는 `review_id`는 중복 저장을 방지하기 위해 skip한다.

MVP 이후에는 기존 리뷰 수정 반영을 위해 다음 확장을 검토한다.

- `content_hash` 기준 리뷰 내용 변경 감지
- `review_updated_at` 기준 변경 감지
- 기존 리뷰 내용이 바뀐 경우 해당 리뷰만 RTI 재분석

현재 로컬 시뮬레이션에는 DB가 연결되어 있지 않으므로 `review_id` 중복 조회와 신규 리뷰 선별은 아직 실행하지 않는다.

## 9. 아직 연결하지 않은 부분

현재는 로컬 검증 단계이며 다음 기능은 아직 구현하지 않았다.

- Redis Queue 실제 연결
- `product_analysis_job` DB 상태 업데이트
- `reviews` 테이블 insert
- `review_trust_scores` 테이블 insert
- Spring API 연동
- Frontend 상태 조회 및 SSE 연결

local job summary의 `RUNNING`, `DONE`, `FAILED`는 실제 DB job 상태가 아니라 Worker 처리 흐름을 검증하기 위한 파일 기반 상태다.

## 10. 다음 구현 순서 제안

1. Redis Queue message schema 최종 확인
2. `product_analysis_job` 상태 컬럼과 에러 메시지 컬럼 확인
3. FastAPI Worker skeleton 추가
4. Queue message 수신 후 local simulation 흐름 호출
5. `reviews` insert 연결
6. `review_trust_scores` insert 연결
7. `DONE` / `FAILED` 상태 업데이트 연결
8. Spring 및 Frontend 상태 조회 흐름과 연결

각 단계에서는 기존 로컬 시뮬레이션의 입력 검증, 단계별 실패 처리 및 summary 상태 기준을 재사용할 수 있는지 확인한다.

## 11. 결론

현재는 NAVER 상품 URL 1개 기준으로 크롤링부터 RTI 분석, local worker job summary 저장까지 검증되었다.

실제 Redis, DB 및 Spring 연결은 아직 하지 않았으며, 다음 단계에서는 기존에 협의한 Queue Worker 구조를 바탕으로 FastAPI Worker skeleton부터 단계적으로 연결하는 것이 적절하다.
