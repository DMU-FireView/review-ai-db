import sqlite3
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

# ==========================================
# 🧠 실제 AI 분석 모듈 임포트 (동환님 코드)
# ==========================================
try:
    from ai.text_analyzer import calculate_text_score
    from ai.behavior_analyzer import calculate_behavior_score
    from ai.network_analyzer import calculate_network_score
    print("✅ 실제 AI 분석 모듈 로드 성공!")
except ImportError as e:
    print(f"⚠️ 경고: 필수 AI 패키지가 누락되었습니다. ({e.name})")
    def calculate_text_score(content, quality_score=None): return 85, []
    def calculate_behavior_score(review): return 90, []
    def calculate_network_score(review): return 88, []
except Exception as e:
    print(f"⚠️ 경고: AI 모듈 로드 중 오류 발생: {e}")
    def calculate_text_score(content, quality_score=None): return 85, []
    def calculate_behavior_score(review): return 90, []
    def calculate_network_score(review): return 88, []


# ==========================================
# 🗄️ SQLite Database 초기화 및 시드 세팅
# ==========================================
DB_FILE = "review_system.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 💡 스키마가 변경되었으므로 기존 테이블 초기화 (테스트 편의성)
    cursor.execute("DROP TABLE IF EXISTS review_trust_scores")
    cursor.execute("DROP TABLE IF EXISTS reviews")
    cursor.execute("DROP TABLE IF EXISTS products")

    print("🚀 [DB 초기화] 최신 스키마로 테이블 생성 및 시드 데이터 주입...")

    # 1. products 테이블 (product_url 추가됨)
    cursor.execute('''
        CREATE TABLE products (
            product_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            product_url TEXT,
            category VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. reviews 테이블 (review_date 추가됨)
    cursor.execute('''
        CREATE TABLE reviews (
            review_id BIGINT PRIMARY KEY,
            product_id VARCHAR(50) NOT NULL,
            user_id VARCHAR(100) NOT NULL,
            rating INT NOT NULL,
            content TEXT NOT NULL,
            review_date DATE NOT NULL,
            verified_purchase BOOLEAN DEFAULT FALSE,
            account_age_days INT,
            reviews_written_today INT,
            similar_review_count INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    ''')

    # 3. review_trust_scores 테이블
    cursor.execute('''
        CREATE TABLE review_trust_scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id BIGINT NOT NULL,
            rti INT NOT NULL,
            level VARCHAR(20) NOT NULL,
            text_score INT NOT NULL,
            behavior_score INT NOT NULL,
            network_score INT NOT NULL,
            reasons TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES reviews(review_id)
        )
    ''')

    # 4. 시드(Seed) 데이터 삽입 (하연님 피드백: 실제 연동 ID 반영)
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    two_days_ago_str = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    cursor.executemany('''
        INSERT INTO products (product_id, name, product_url, category)
        VALUES (?, ?, ?, ?)
    ''', [
        ('53530143052', 'SOUNDPRO ANC 노이즈캔슬링 블루투스 이어폰 X7 Pro', 'https://smartstore.naver.com/main/products/11590446932', '전자기기'),
        ('p002', '무선 블루투스 이어폰 Basic', 'https://smartstore.naver.com/main/products/0002', '전자기기')
    ])

    # Trend 테스트를 위해 날짜를 어제/오늘로 분산
    cursor.executemany('''
        INSERT INTO reviews (
            review_id, product_id, user_id, rating, content, review_date,
            verified_purchase, account_age_days, reviews_written_today, similar_review_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        (1, '53530143052', 'reviewer_0099', 5, '이 제품 정말 최고예요. 품질 완전 대박. 이런 제품은 처음봐요. 품질 완전 대박. 강력추천!!', today_str, False, 2, 12, 8),
        (2, '53530143052', 'kim_realbuyer', 4, '배송도 빠르고 품질도 좋네요. 다만 색상이 사진과 조금 달라서 별 하나 뺐어요. ANC 성능은 지하철에서 꽤 괜찮았습니다.', yesterday_str, True, 540, 1, 0),
        (3, '53530143052', 'new_user_102', 5, '전반적으로 만족합니다. 음질도 괜찮고 착용감도 좋아요. 추천드립니다.', two_days_ago_str, False, 15, 3, 1)
    ])

    conn.commit()
    conn.close()
    print("✅ [DB 세팅 완료] review_system.db 준비 끝!")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # v1: 서버 시작 시 DB를 자동 초기화하지 않습니다.
    # 테이블 생성 및 seed 삽입은 scripts/load_seed.py에서 수동 실행합니다.
    yield

app = FastAPI(
    title="Re:view AI Analysis Server (Real DB & Trend Integrated)", 
    version="v13.0",
    lifespan=lifespan
)


# ==========================================
# 1. 🚀 Request 스키마 (초경량 트리거 규격)
# ==========================================
class TriggerRequest(BaseModel):
    product_id: str = Field(..., description="조회할 상품의 고유 식별자 (상품ID)")
    url: Optional[str] = Field(None, description="상품 URL (page_url, product_url 호환)")
    page_url: Optional[str] = None
    product_url: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "53530143052",
                "url": "https://smartstore.naver.com/main/products/11590446932"
            }
        }
    }

# ==========================================
# 2. 내부 데이터 파싱 모델 (AI 엔진 입력용)
# ==========================================
class ReviewInput(BaseModel):
    review_id: str
    product_id: str
    user_id: str
    content: str
    review_date: str # 💡 추가됨: Trend 산출용
    rating: int = 5
    image_count: int = 0
    quality_score: Optional[float] = None
    verified_purchase: Any = "unknown"
    repurchase: Any = "unknown"
    free_trial: Any = "unknown"
    reviews_written_today: int = 1
    similar_review_count: int = 0

# ==========================================
# 3. Response 스키마 (MVP 사양 - percentage 삭제 반영)
# ==========================================
class SignalScores(BaseModel):
    text: int
    behavior: int
    network: int

class ReasonObject(BaseModel):
    code: str
    message: str

class InputFeatures(BaseModel):
    image_count: int
    quality_score: Optional[float] = None
    verified_purchase: str = "unknown"
    repurchase: str = "unknown"
    free_trial: str = "unknown"
    reviews_written_today: int = 1
    similar_review_count: int = 0

class ProductSummaryResult(BaseModel):
    product_id: str
    average_rti: float
    level: str
    review_count: int
    safe_count: int
    warn_count: int
    danger_count: int

class SummaryResponse(BaseModel):
    products: List[ProductSummaryResult]

class AnalysisResult(BaseModel):
    review_id: str
    rti: int
    level: str
    signals: SignalScores
    input_features: InputFeatures
    reasons: List[ReasonObject]

class BatchResponse(BaseModel):
    results: List[AnalysisResult]

class TrendItem(BaseModel):
    date: str
    average_rti: float
    review_count: int
    safe_count: int
    warn_count: int
    danger_count: int

class TrendResponse(BaseModel):
    trend: List[TrendItem]

class ReasonDetail(BaseModel):
    title: str
    description: str
    # 💡 percentage 필드 삭제 (하연님 피드백 반영)

class ReviewReportResponse(BaseModel):
    review_id: str
    rti: int
    signals: SignalScores
    reasons: List[ReasonDetail]

class SummaryStat(BaseModel):
    total_reviews: int
    average_rti: float
    danger_count: int
    warn_count: int  
    safe_count: int

class SampleReview(BaseModel):
    review_id: str
    author: str
    date: str
    rating: int
    content: str
    level: str
    reasons: List[ReasonObject]

class ProductRiskReportResponse(BaseModel):
    product_id: str
    product_name: str
    summary_stat: SummaryStat
    trend: List[TrendItem]
    sample_reviews: List[SampleReview]


# ==========================================
# 4. 🧠 코어 분석 엔진 통합 함수
# ==========================================
def analyze_single_review(review: ReviewInput) -> AnalysisResult:
    t_score, t_reasons = calculate_text_score(review.content, review.quality_score)
    
    review_dict = review.model_dump()
    b_score, b_reasons = calculate_behavior_score(review_dict)
    n_score, n_reasons = calculate_network_score(review_dict)
    
    rti_score = round(t_score * 0.4 + b_score * 0.35 + n_score * 0.25)
    
    if rti_score < 50: level = "danger"
    elif rti_score < 80: level = "warn"
    else: level = "safe"
        
    all_raw_reasons = t_reasons + b_reasons + n_reasons
    combined_reasons = [ReasonObject(code=r["code"], message=r["message"]) for r in all_raw_reasons]
    
    return AnalysisResult(
        review_id=review.review_id,
        rti=rti_score,
        level=level,
        signals=SignalScores(text=int(t_score), behavior=int(b_score), network=int(n_score)),
        input_features=InputFeatures(
            image_count=review.image_count, quality_score=review.quality_score,
            verified_purchase=str(review.verified_purchase), repurchase=str(review.repurchase),
            free_trial=str(review.free_trial), reviews_written_today=review.reviews_written_today,
            similar_review_count=review.similar_review_count
        ),
        reasons=combined_reasons
    )

# ==========================================
# 5. 🗄️ 실제 DB 연동 로직 (URL 호환 및 날짜 포함)
# ==========================================
def get_target_product_id(payload: TriggerRequest) -> str:
    """DB에서 product_id를 찾거나, 못 찾으면 url을 이용해 역추적합니다."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    target_id = payload.product_id

    c.execute("SELECT product_id FROM products WHERE product_id = ?", (target_id,))
    if not c.fetchone():
        target_url = payload.url or payload.page_url or payload.product_url
        if target_url:
            c.execute("SELECT product_id FROM products WHERE product_url = ?", (target_url,))
            row = c.fetchone()
            if row:
                target_id = row[0]
    conn.close()
    return target_id

def fetch_raw_reviews_from_db(payload: TriggerRequest) -> List[ReviewInput]:
    target_id = get_target_product_id(payload)
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE product_id = ?", (target_id,))
    rows = cursor.fetchall()
    conn.close()

    reviews = []
    for row in rows:
        ver_pur = True if row["verified_purchase"] else False
        r_input = ReviewInput(
            review_id=str(row["review_id"]),
            product_id=row["product_id"],
            content=row["content"],
            rating=row["rating"],
            user_id=row["user_id"],
            review_date=row["review_date"], # 💡 실제 날짜
            verified_purchase=ver_pur,
            reviews_written_today=row["reviews_written_today"] or 1,
            similar_review_count=row["similar_review_count"] or 0,
            image_count=0, quality_score=0.5,
            repurchase="unknown", free_trial="unknown"
        )
        reviews.append(r_input)
    return reviews

def calculate_real_trend(results: List[AnalysisResult], raw_data: List[ReviewInput]) -> List[TrendItem]:
    """💡 랜덤을 제거하고 100% 실제 날짜 및 점수 기반 30일 추이를 계산합니다."""
    trend_dict = defaultdict(lambda: {"rti_sum": 0, "count": 0, "safe": 0, "warn": 0, "danger": 0})
    
    for res, raw in zip(results, raw_data):
        date_str = raw.review_date[:10]
        trend_dict[date_str]["count"] += 1
        trend_dict[date_str]["rti_sum"] += res.rti
        if res.level == "safe": trend_dict[date_str]["safe"] += 1
        elif res.level == "warn": trend_dict[date_str]["warn"] += 1
        else: trend_dict[date_str]["danger"] += 1

    trend_data = []
    today = datetime.now().date()
    for i in range(29, -1, -1):
        target_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        data = trend_dict.get(target_date, {"rti_sum": 0, "count": 0, "safe": 0, "warn": 0, "danger": 0})
        avg_rti = round(data["rti_sum"] / data["count"], 2) if data["count"] > 0 else 0.0
        
        trend_data.append(TrendItem(
            date=target_date,
            average_rti=avg_rti,
            review_count=data["count"],
            safe_count=data["safe"],
            warn_count=data["warn"],
            danger_count=data["danger"]
        ))
    return trend_data


# ==========================================
# 6. API Endpoints (5개 API)
# ==========================================

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["AI Analysis"])
async def analyze_rti_summary(payload: TriggerRequest):
    raw_data = fetch_raw_reviews_from_db(payload)
    results = [analyze_single_review(r) for r in raw_data]
    
    if not results: return {"products": []}
        
    avg_rti = round(sum(r.rti for r in results) / len(results), 2)
    safe_cnt = sum(1 for r in results if r.level == "safe")
    warn_cnt = sum(1 for r in results if r.level == "warn")
    danger_cnt = sum(1 for r in results if r.level == "danger")
    overall_level = "danger" if danger_cnt > 0 else ("warn" if warn_cnt > 0 else "safe")
    
    return {"products": [{
        "product_id": get_target_product_id(payload),
        "average_rti": avg_rti, "level": overall_level, "review_count": len(results),
        "safe_count": safe_cnt, "warn_count": warn_cnt, "danger_count": danger_cnt
    }]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=BatchResponse, tags=["AI Analysis"])
async def analyze_reviews_detail(payload: TriggerRequest):
    raw_data = fetch_raw_reviews_from_db(payload)
    results = [analyze_single_review(r) for r in raw_data]
    return {"results": results}

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["AI Analysis"])
async def get_rti_trend(payload: TriggerRequest):
    raw_data = fetch_raw_reviews_from_db(payload)
    results = [analyze_single_review(r) for r in raw_data]
    
    # 💡 100% 리얼 데이터 기반 트렌드 산출
    real_trend = calculate_real_trend(results, raw_data)
    return {"trend": real_trend}

@app.post("/api/internal/ai/reviews/report", response_model=ReviewReportResponse, tags=["AI Reporting"])
async def get_review_detail_report(payload: TriggerRequest):
    raw_data = fetch_raw_reviews_from_db(payload)
    if not raw_data:
        return {"review_id": "unknown", "rti": 100, "signals": {"text":100, "behavior":100, "network":100}, "reasons": []}

    results = [analyze_single_review(r) for r in raw_data]
    target_result = next((r for r in results if r.level == "danger"), results[0])
    
    ui_reasons = []
    for r in target_result.reasons:
        ui_reasons.append(ReasonDetail(
            title=r.message,
            description=f"[{r.code}] 분석 엔진 감지 결과"
            # 💡 percentage 랜덤값 완전 삭제 (하연님 피드백 반영)
        ))
        
    return {
        "review_id": target_result.review_id,
        "rti": target_result.rti,
        "signals": target_result.signals,
        "reasons": ui_reasons
    }

@app.post("/api/internal/ai/products/risk-report", response_model=ProductRiskReportResponse, tags=["AI Reporting"])
async def get_product_risk_report(payload: TriggerRequest):
    raw_data = fetch_raw_reviews_from_db(payload)
    results = [analyze_single_review(r) for r in raw_data]
    target_id = get_target_product_id(payload)
    
    if not results:
        return ProductRiskReportResponse(
            product_id=target_id, product_name="데이터 없음",
            summary_stat=SummaryStat(total_reviews=0, average_rti=0.0, danger_count=0, warn_count=0, safe_count=0),
            trend=[], sample_reviews=[]
        )

    avg_rti = round(sum(r.rti for r in results) / len(results), 2)
    safe_cnt = sum(1 for r in results if r.level == "safe")
    warn_cnt = sum(1 for r in results if r.level == "warn")
    danger_cnt = sum(1 for r in results if r.level == "danger")
    
    sample_revs = []
    for res, raw in zip(results, raw_data):
        if res.level in ["danger", "warn"]:
            sample_revs.append(SampleReview(
                review_id=res.review_id,
                author=raw.user_id,
                date=raw.review_date.replace("-", "."), # 💡 DB 진짜 날짜
                rating=raw.rating,
                content=raw.content,
                level=res.level,
                reasons=res.reasons
            ))
            
    real_trend = calculate_real_trend(results, raw_data)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM products WHERE product_id = ?", (target_id,))
    prod_row = c.fetchone()
    conn.close()
    prod_name = prod_row[0] if prod_row else f"알 수 없는 상품 ({target_id})"

    return ProductRiskReportResponse(
        product_id=target_id, product_name=prod_name,
        summary_stat=SummaryStat(
            total_reviews=len(results), average_rti=avg_rti,
            danger_count=danger_cnt, warn_count=warn_cnt, safe_count=safe_cnt
        ),
        trend=real_trend, sample_reviews=sample_revs
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)