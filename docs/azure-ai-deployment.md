<!-- 새 Azure Ubuntu VM의 AI 서비스 최초 설치와 자동 배포 절차. -->
# Azure for Students 배포

> 2026-09-09: 현재 코드는 전용 SQLite 결과 저장 볼륨(ai-results)을 사용합니다.
> DB 파일 백업/보존 정책을 확정해야 하며 실험 수집/SSE API는 운영에서 OFF로 유지하세요.
> 이번 변경의 Docker 빌드는 Linux 엔진 미실행으로 재검증하지 못했습니다.
> 이전 검증 기록과 구분하고 [통합 준비 상태](integration-preparation.md)를 먼저 확인하세요.

대상: Ubuntu Server 24.04 LTS x64, reviewadmin, /home/reviewadmin/review-ai-db.
VM 생성과 GitHub Secrets 변경은 사용자가 수행한다.
NSG 포트는 SSH 22와 AI HTTP 8000이며, 8000은 가능한 Data 서버 출발지만
허용한다. DB 3306/5432와 Redis 6379는 AI 서버에 필요 없다.
현재 API에는 인증이 없으므로 접근 허용 범위를 팀에서 확정한다.

## 최초 한 번: 새 VM에서 reviewadmin으로 실행

Docker 공식 Ubuntu 설치 문서의 apt 저장소 방식을 사용한다:
[Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).
아래 명령은 Docker가 없는 새 Ubuntu VM 기준이다.

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
cd /home/reviewadmin
git clone --branch main https://github.com/DMU-FireView/review-ai-db.git
cd /home/reviewadmin/review-ai-db
sudo docker compose config --quiet
sudo docker compose up -d --build
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/api/v1/analyze -H 'Content-Type: application/json' -d '{"product_id":"A001","reviews":[{"review_id":"1001","content":"배송 빠르고 제품도 좋아요","user_id":"user1","review_date":"2026-09-08","verified_purchase":true}]}'
```

먼저 리팩터링을 main에 반영해야 위 main clone으로 새 서비스가 실행된다.
기존 디렉터리가 있다면 clone을 반복하지 말고 브랜치와 로컬 변경을 확인한다.
비공개 저장소라면 VM의 git pull에 필요한 읽기 인증을 별도로 설정한다.
토큰을 remote URL이나 workflow에 하드코딩하지 않는다.

SSH 배포는 sudo 비밀번호 프롬프트 없이 docker compose를 실행할 수 있어야 한다.
VM 관리자가 권한을 준비하고 `sudo -n docker compose version`으로 확인한다.
AZURE_PASSWORD는 SSH 인증용이며 sudo 프롬프트에는 자동 전달되지 않는다.

## Repository Secrets와 자동 배포

- AZURE_HOST: 새 VM 공인 IP
- AZURE_USER: reviewadmin
- AZURE_PASSWORD: 새 VM SSH 비밀번호

DB_PORT, DB_HOST_PORT, DB_PASSWORD, REDIS_PASSWORD는 더 이상 사용하지 않는다.
GitHub에 저장된 기존 secret 값 자체는 이번 작업에서 삭제하지 않았다.

main push → Python 3.12 pytest → Compose 설정·빌드 검증 → SSH →
main 브랜치 확인 → git pull --ff-only origin main →
sudo docker compose up -d --build → health 재시도 검사.

workflow는 .env를 생성하거나 덮어쓰지 않는다.
선택적 Google 인증은 README의 읽기 전용 마운트를 사용한다.
VM의 docker-compose.override.yml에 설정하면 자동 배포 명령에도 적용된다.
컨테이너 교체 시 짧은 중단이 있을 수 있다.
기존 VM의 DB/Redis 컨테이너·볼륨은 자동 삭제하지 않는다.

## 검증 상태

2026-09-08: Python 3.12 pytest 22개(실제 Uvicorn HTTP 포함), pip check,
docker compose config 통과.
Linux 엔진 시작 후 docker compose build/up/ps와 시작 로그 검증도 통과했다.
review-ai는 healthy, 재시작 0회이며 startup error가 없었다.
localhost:8000의 health와 analyze는 HTTP 200, 예제 점수는 88/safe였다.
기존 review_ai_db orphan 경고는 공유 인프라 보존을 위해 그대로 두었다.
