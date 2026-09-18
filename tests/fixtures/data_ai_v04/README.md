# Data/AI v0.4 합성 결과 샘플

실제 크롤링 데이터·개인정보·모델 실행 결과가 아닌 **계약/매핑 테스트용 가짜 데이터**입니다.
점수·등급은 명시적으로 지정한 값이며, RTI 공식이나 가중치 검증의 정답이 아닙니다.
특히 일부 신호가 없는 경우의 RTI 계산 정책은 아직 합의되지 않았습니다.

| 사례 | 매퍼 입력 | 목표 응답 | 확인할 상태 |
| --- | --- | --- | --- |
| 정상 결과 | [입력](normal.mapping-input.json) | [응답](normal.response.json) | 세 신호 가용, 리뷰 2건, 분석 결과 역순, 빈/비어 있지 않은 reasons |
| 행동 근거 부족 | [입력](behavior_unavailable.mapping-input.json) | [응답](behavior_unavailable.response.json) | behavior unavailable, score=null, 나머지 신호 가용 |
| 비교 리뷰 부족 | [입력](network_unavailable.mapping-input.json) | [응답](network_unavailable.response.json) | network unavailable, score=null, 나머지 신호 가용 |
| 모든 신호 계산 불가 | [입력](all_unavailable.mapping-input.json) | [응답](all_unavailable.response.json) | 세 신호 unavailable, rti_available=false, rti/level=null |

## 파일 사용법

- `*.mapping-input.json`은 **내부 매퍼의 입력**입니다. `requested`는 원본 식별자 목록,
  `evaluated`는 명시적으로 주어진 분석 결과입니다. Data → AI HTTP 요청 본문이 아닙니다.
- `*.response.json`은 v0.4 검토용 모델의 목표 응답 예시입니다. 현재
  `POST /api/v1/analyze` 응답이 이 형식으로 바뀐 것은 아닙니다.
- 0이 포함된 ID와 콜론을 그대로 보존합니다. 없는 신호의 null을 0 또는 100으로 대체하지 않습니다.
- reason/unavailable reason 코드는 합성 사례용이며 최종 코드 목록을 확정하지 않습니다.
- 모든 신호 unavailable 사례는 이미 판정된 결과를 표현합니다. 빈 본문 수용이나 모델 장애를
  정상 결과로 숨기는 정책을 의미하지 않습니다.
- 기존 모델은 편의 필드 `review_count`를 요구하므로 샘플에도 포함합니다.
  PDF에서는 선택 필드이며, 실제 필수 여부는 최종 계약 합의 사항입니다.

프로젝트 루트에서:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_data_ai_contract_fixtures.py -q
```

테스트는 파일을 읽어 검증한 뒤 순수 매퍼의 전체 출력과 기대 응답 JSON을 비교합니다.
null/가용성 조합, 필수 필드 누락, 다른 식별자 연결 같은 잘못된 변형도 거절하는지 확인합니다.
외부 API·크롤러·DB·분석 모델 호출은 하지 않습니다.

배경: [계약 차이·협의 질문](../../../docs/data-ai-contract-v04-review.md).
