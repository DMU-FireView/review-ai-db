<!-- PR #28의 main 충돌 해결 근거와 보존한 기존 스키마를 기록한다. -->
# main 병합 충돌 해결

대상은 작업 브랜치 750b696과 main 064ad5d이다. main을 작업 브랜치에 병합하며
현재 Data v0.5 분석·MySQL 저장·Redis 비활성화 결정을 기준으로 충돌을 해결했다.
이 병합은 운영 배포나 PR의 main 병합을 실행하는 작업이 아니다.

| 파일 | 비교 결과 및 해결 |
| --- | --- |
| .github/workflows/ci.yml | 현재 pytest·Compose 검사·빌드 후 배포, 고정 action 버전, ff-only pull을 유지한다. main의 .env 덮어쓰기 방식은 새 인증 설정을 지울 수 있어 복원하지 않는다. |
| db/schema.sql | products/reviews/review_trust_scores/product_analysis_job 정의는 양쪽이 동일하다. 전부 보존하고 잘못된 SQLite 설명만 MySQL로 정정한다. |
| docker-compose.yml | 기존 ai-db 서비스 이름과 ai-db-data 볼륨은 유지한다. 현재 AI·MySQL 구성과 인증 환경변수를 보존하고 사용하지 않는 Redis 자동 실행은 복원하지 않는다. |
| worker/redis_consumer.py | main의 코드는 BLPOP 후 실제 분석·저장 대신 진행 메시지를 출력하는 뼈대다. 메시지만 소비할 위험이 있어 현재 deprecated 진입점을 유지한다. |

main의 원래 변경은 병합 부모와 Git 이력에 보존된다.
- f0fc082: 과거 배포 환경변수 주입
- 3a36ab2: 기존 MySQL 스키마 공백 정리
- 886ffe6: Redis Worker 뼈대
- 064ad5d: Redis Compose 구성

기존 DB나 Docker 볼륨에 SQL을 실행하지 않았으며 비밀번호·실제 토큰도 수정하지 않았다.
PR을 main에 병합하면 기존 workflow의 main push 배포가 실행될 수 있다.
클라우드가 중단된 상태이므로 병합 전 GitHub Actions 배포 대상·Secrets·VM의 .env 준비 상태를 확인해야 한다.
