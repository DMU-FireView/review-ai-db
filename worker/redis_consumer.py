import json
import redis
import time
import os

# 환경 변수에서 주소와 비밀번호를 자동으로 가져옵니다.
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None) # 💡 비밀번호 추가!
QUEUE_NAME = "review_analysis_queue"

def get_redis_client():
    # 💡 연결할 때 password를 넣고 접속하도록 수정!
    return redis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        password=REDIS_PASSWORD, 
        db=0, 
        decode_responses=True
    )

def start_worker():
    redis_client = get_redis_client()
    print(f"🚀 FastAPI Worker 시작... Redis({REDIS_HOST}:{REDIS_PORT}) 큐 대기 중")
    
    while True:
        try:
            # 1. Queue 수신 (메시지가 올 때까지 무한 대기)
            _, message = redis_client.blpop(QUEUE_NAME)
            job_data = json.loads(message)
            
            job_id = job_data.get('jobId')
            product_url = job_data.get('productUrl')
            platform = job_data.get('platform', 'NAVER')
            
            print(f"📦 새로운 Job 수신! Job ID: {job_id} | URL: {product_url}")
            
            # ---------------------------------------------------------
            # 💡 팀원들이 채워 넣을 핵심 비즈니스 로직
            # ---------------------------------------------------------
            
            # [DB] 1. job 상태를 RUNNING으로 업데이트
            print(f"⏳ Job {job_id}: 상태를 RUNNING으로 변경합니다...")
            
            # [Crawler] 2. productUrl 크롤링 실행 및 raw reviews 생성
            print(f"🕵️‍♂️ Job {job_id}: 리뷰 크롤링 시작...")
            
            # [DB] 3 & 4. reviews 테이블에 insert (새로운 리뷰만 Batch Insert!)
            print(f"💾 Job {job_id}: DB에 신규 리뷰 Insert 진행...")
            
            # [AI] 5. 신규 리뷰들을 KoELECTRA 모델로 RTI 분석
            print(f"🧠 Job {job_id}: RTI AI 감성 분석 중...")
            
            # [DB] 6. 분석 결과를 review_trust_scores 테이블에 저장
            print(f"📊 Job {job_id}: RTI 점수 DB 저장 완료...")
            
            # [DB] 7. job 상태를 DONE으로 업데이트
            print(f"✅ Job {job_id}: 모든 처리 완료! 상태를 DONE으로 변경합니다.")
            print("-" * 50)
            
        except Exception as e:
            print(f"❌ Job 처리 중 에러 발생: {str(e)}")
            time.sleep(2)

if __name__ == "__main__":
    start_worker()