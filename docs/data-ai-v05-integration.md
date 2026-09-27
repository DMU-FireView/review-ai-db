<!-- v0.5 결과 계약과 Data Swagger를 기준으로 구현한 API·인증·분석 정책을 설명한다. -->
# Data AI v0.5 연동

## 적용 범위

2026-09-27의 `[Update1]ReView_Data_AI_Result.docx` 검토본과 Data 서버 OpenAPI를 참고했다.
사용자가 팀원 분석기 전환(50/30/20, 가용 신호 재정규화), 80 이상 safe, AI 자체 DB 유지를 승인했다.
문서의 76/safe 예시는 따르지 않는다. API 경로와 운영 배치는 Data 담당자의 최종 확인이 필요하다.

| 경로 | 입력·응답 | 계산 |
| --- | --- | --- |
| POST /api/v1/data/analyze | v0.5 정규화 리뷰 → 평면 결과 | 팀원 분석기, 기본 가중치 .5/.3/.2, 가용 신호로 재정규화 |
| POST /api/v1/analyze | 기존 필수 user_id/review_date와 기존 응답 유지 | 호환용 .4/.35/.25, Python round |
| POST /experimental/analysis/collect/stream | 수집 진행 SSE → 최종 v0.5 result | 새 Data 분석과 같은 분석기, 기본 OFF |

세 경로 모두 입력·결과를 AI 자체 MySQL에 저장한다. DB 커밋 후에만 성공 결과를 반환한다.
새 경로는 계산 완료 응답 방식이며 202 접수·백그라운드 큐·콜백 방식이 아니다.
Data의 결과 DB에 직접 쓰지 않고 결과 JSON을 응답한다. 별도 결과 수신 URL은 추측해 만들지 않았다.

## 요청과 결과

```json
{
  "platform": "mall",
  "product_id": "0007",
  "reviews": [{
    "review_id": "00:01",
    "content": "배송 빠르고 제품도 좋아요",
    "rating": 5,
    "written_at": "2026-09-27T12:00:00"
  }]
}
```

```json
{
  "platform": "mall",
  "product_id": "0007",
  "review_count": 1,
  "results": [{
    "review_id": "00:01",
    "rti": 75.0,
    "level": "warn",
    "text_score": 75.0,
    "behavior_score": null,
    "network_score": null,
    "reasons": ["SHORT_REVIEW"]
  }]
}
```

- platform/product_id/review_id는 문자열 그대로 보존한다. 숫자 변환·trim·접두사 추가를 하지 않는다.
- 한 요청은 한 상품, 리뷰 1~500개다. 500개는 O(n²) 비교 비용을 제한하는 우리 서버의 상한이며 운영 합의가 필요하다.
- 같은 review_id를 두 번 보내면 422다. 결과는 요청 순서대로 정확히 매칭한다.
- rating/written_at은 선택이며 원본 저장에 보존한다. rating은 현재 분석 입력에 사용하지 않는다.
- 최소 입력에는 구매 인증·안정적인 사용자 ID·작성 이력이 없으므로 behavior_score는 null이다.
  written_at만으로 행동 점수를 만들지 않는다. SSE의 표시용 author로 사용자 동일성을 추측하지 않는다.
- network는 같은 배치의 다른 리뷰 본문을 비교한다. 공백·대소문자 정규화 후 동일 여부 기반이며 의미 임베딩 모델이 아니다.
- RTI는 사용 가능한 신호의 기본 가중치를 합계 1로 재정규화해 계산한다. 정수 반올림하지 않는다.
- level은 RTI 80 이상 safe, 50 이상 warn, 그 미만 danger다.
- reasons는 분석기가 만든 코드의 순서·문자열을 그대로 보존한다. TEXT_* 등 예시 접두사를 임의 추가하지 않는다.
- 근거 부족 null은 정상 분석 결과다. 요청 오류는 422, 분석·저장 실패는 503으로 구분한다.
- 모든 신호 부재 시 rti/level=null을 표현할 수 있다. 현재 텍스트 baseline은 유효한 본문에 점수를 내므로
  실제 정상 API 입력에서 모든 신호 부재가 반드시 발생하는 것은 아니다.

## 인증과 TLS

분석 API와 실험 API는 `X-Internal-Token` 헤더를 검사한다. `/health`는 Docker 상태 확인용으로 인증 없이 유지한다.

```dotenv
# 실제 값은 .env 또는 배포 비밀 저장소에서 설정하며 Git에 넣지 않는다.
REQUIRE_INTERNAL_TOKEN=1
INTERNAL_TOKEN=
DATA_SERVER_BASE_URL=
DATA_INTERNAL_TOKEN=
ENABLE_EXPERIMENTAL_COLLECTION=0
```

- 운영에서는 REQUIRE_INTERNAL_TOKEN=1과 유효한 INTERNAL_TOKEN을 함께 설정해야 한다. 없으면 시작 실패한다.
- REQUIRE_INTERNAL_TOKEN=0이고 토큰도 없을 때만 기존 로컬 무인증 동작을 유지한다.
- DATA_INTERNAL_TOKEN은 AI → Data 요청용이다. 비어 있으면 INTERNAL_TOKEN을 재사용한다.
- DATA_SERVER_BASE_URL은 확정된 HTTPS 주소로 설정한다. 비어 있을 때만 과거 CRAWLER_BASE_URL을 읽는다.
- 토큰을 사용하는 Data SSE 수신기는 HTTP를 거부한다. 리다이렉트를 따라가지 않고 타 호스트 경로도 거부한다.
- 실제 공유 토큰은 이번 코드·테스트·문서에 저장하지 않았다. 테스트는 가짜 토큰만 사용한다.
- AI의 외부 공개 주소에도 TLS termination이 필요하다. 이 앱이 인증서나 프록시를 자동 설치하지는 않는다.
- `docker compose config`는 환경변수의 비밀 값을 펼칠 수 있으므로 검사는 `--quiet`를 사용한다.

## SSE와 Swagger 확인 범위

확인한 Data OpenAPI: `http://34.50.27.128:8000/openapi.json`, title=review-data, version=0.1.0.
공개 명세만 인증 없이 읽었고 실제 리뷰 수집이나 토큰 전송은 하지 않았다.

- GET /{platform}/products/{product_id}/reviews/stream, limit, Last-Event-ID, X-Internal-Token은 확인했다.
- 응답 상세 필드는 명세에 비어 있으므로 기존 review/progress/done/error/heartbeat payload의 실샘플 확인이 필요하다.
- SSE는 수집 중 진행 상황을 전달하고, done 이후 전체 배치를 한 번 분석한다. 새 모델의 최종 결과는 v0.5 평면 형식이다.
- 수집·분석 중 heartbeat와 DB 저장 선행, 중복 검증, 연결 종료 후 이미 시작한 분석의 저장 동작을 유지한다.
- ALLOW_LEGACY_CRAWLER_DEFAULTS는 새 SSE 경로에서 더 이상 사용하지 않는다. 빈 근거의 기본 점수를 생성하지 않는다.
- product_key로 여러 상품을 묶는 요청은 422다. 원본 platform/product_id 단위만 허용한다.
- Data의 GET /api/v1/jobs/{job_id}는 정수 ID, AI의 X-Analysis-Job-ID는 UUID다. 동일 ID라고 간주하지 않는다.
- CRAWLER_MAX_RETRIES는 기본 0이다. Last-Event-ID가 영구 재개·멱등 처리를 보장하지 않는다.

## 분석기 출처와 검증 한계

출처: DMU-FireView/review-ai-new `c48b7e566bf8e5d4c832c2fcad64da4406af707e`.
app/analyzers, app/scoring, integrations/sentiment·similarity의 계산 구현을 가져왔다.
services/analysis는 이름 충돌을 피해 services/team_analysis로 두고 관련 회귀 테스트도 함께 가져왔다.
KoELECTRA 학습·진단 코드는 가져오지 않았으며 이 API에 학습 모델이나 Google 감성 서비스를 자동 연결하지 않는다.

테스트는 격리 SQLite 저장소와 모의 Data SSE로 실행한다. 실제 MySQL·GCP HTTPS·Data 왕복 연결 검증을 대신하지 않는다.
이번 검증은 전체 pytest 237개 통과·실제 MySQL 테스트 1개 보류, 실제 로컬 TCP HTTP와 Compose 설정 검사 통과다.
기존 호환 API 점수 88과 새 Data API 점수 75(동일 짧은 본문·비교 근거 없음)를 각각 회귀 검증했다.
DB 작업 중단 상태는 유지한다. 새 클라우드 계정, 확정 HTTPS 주소, 실제 입력/SSE 샘플을 받은 뒤 배포 검증해야 한다.
v0.4 검토용 모델·문서·샘플은 과거 비교용으로 보존하며 새 API 응답으로 사용하지 않는다.
