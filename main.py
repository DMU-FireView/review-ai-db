from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import random

# 기존 프로젝트의 AI 분석 모듈 로드 (실제 환경에 맞게 유지)
try:
    from ai.text_analyzer import calculate_text_score
    from ai.behavior_analyzer import calculate_behavior_score
    from ai.network_analyzer import calculate_network_score
except ImportError:
    # 로컬/스웨거 테스트 시 모듈이 없어도 에러가 나지 않도록 방어
    def calculate_text_score(content, score): return 85, []
    def calculate_behavior_score(data): return 90, []
    def calculate_network_score(data): return 88, []

app = FastAPI(title="Re:view AI Analysis Server (v0 MVP Edition)", version="v10.2")


# ==========================================
# 1. 🚀 Request 스키마 (초경량 트리거 규격)
# ==========================================
class TriggerRequest(BaseModel):
    product_id: str = Field(..., description="조회할 상품의 고유 식별자 (상품ID)")
    url: Optional[str] = Field(None, description="상품 URL (page_url, product_url 호환)")
    page_url: Optional[str] = None
    product_url: Optional[str] = None
    # review_id 완전히 제거 완료

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "53530143052",
                "url": "https://smartstore.naver.com/main/products/11590446932"
            }
        }
    }


# ==========================================
# 2. Response 스키마 (미구현 항목 제외 다이어트 버전)
# ==========================================

# --- [공통 하위 모델] ---
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


# --- [API 1: product-list 응답] ---
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


# --- [API 2: product-detail 응답] ---
class AnalysisResult(BaseModel):
    review_id: str
    rti: int
    level: str
    signals: SignalScores
    input_features: InputFeatures
    reasons: List[ReasonObject]

class BatchResponse(BaseModel):
    results: List[AnalysisResult]


# --- [API 3: rti-trend 응답] ---
class TrendItem(BaseModel):
    date: str
    average_rti: float
    review_count: int
    safe_count: int
    warn_count: int
    danger_count: int

class TrendResponse(BaseModel):
    trend: List[TrendItem]


# --- [API 4: 리뷰 상세 리포트 응답 모델] ---
class ReasonDetail(BaseModel):
    title: str
    description: str
    percentage: str

class ReviewReportResponse(BaseModel):
    review_id: str
    rti: int
    signals: SignalScores
    reasons: List[ReasonDetail]


# --- [API 5: 상품 위험도 리포트 응답 모델] ---
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
# 3. 데이터 Mocking 로직
# ==========================================
def mock_fetch_reviews_from_db_or_crawler(product_id: str, url: str):
    return [
        {
            "review_id": f"rev_{product_id}_01", "content": "배송도 빠르고 제품 품질도 괜찮았습니다.", 
            "quality_score": 0.76, "image_count": 3
        },
        {
            "review_id": f"rev_{product_id}_02", "content": "진짜 최고예요!!! 완전 강력추천!!! 최고 최고 최고!!!", 
            "quality_score": 0.25, "image_count": 0
        }
    ]


# ==========================================
# 4. API Endpoints (5개 API 모두 POST 및 TriggerRequest 통일)
# ==========================================

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["AI Analysis"])
async def analyze_rti_summary(payload: TriggerRequest):
    """
    [API 1] 상품 요약: product_id를 받아 해당 상품 전체 통계를 반환합니다.
    """
    return {"products": [{
        "product_id": payload.product_id,
        "average_rti": 62.0,
        "level": "warn",
        "review_count": 174,
        "safe_count": 82,
        "warn_count": 54,
        "danger_count": 38
    }]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=BatchResponse, tags=["AI Analysis"])
async def analyze_reviews_detail(payload: TriggerRequest):
    """
    [API 2] 리뷰 상세 분석
    """
    target_url = payload.url or payload.page_url or payload.product_url
    reviews = mock_fetch_reviews_from_db_or_crawler(payload.product_id, target_url)
    
    results = []
    for r in reviews:
        results.append(AnalysisResult(
            review_id=r["review_id"],
            rti=54 if "02" in r["review_id"] else 88,
            level="danger" if "02" in r["review_id"] else "safe",
            signals=SignalScores(text=12, behavior=22, network=20),
            input_features=InputFeatures(image_count=r["image_count"], quality_score=r["quality_score"]),
            reasons=[
                ReasonObject(code="REPETITIVE_KEYWORD", message="반복 문구 밀도 높음"),
                ReasonObject(code="PURCHASE_UNKNOWN", message="구매 이력 확인 불가")
            ]
        ))
        
    return {"results": results}

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["AI Analysis"])
async def get_rti_trend(payload: TriggerRequest):
    """
    [API 3] 위험도 추이: product_id를 받아 과거 30일치 통계를 반환합니다.
    """
    trend_data = []
    today = datetime.now().date()
    
    for i in range(29, -1, -1):
        target_date = today - timedelta(days=i)
        trend_data.append(TrendItem(
            date=target_date.strftime("%Y-%m-%d"),
            average_rti=86.0, review_count=1, safe_count=0, warn_count=1, danger_count=0
        ))
        
    return {"trend": trend_data}

@app.post("/api/internal/ai/reviews/report", response_model=ReviewReportResponse, tags=["AI Reporting"])
async def get_review_detail_report(payload: TriggerRequest):
    """
    [API 4] 리뷰 상세 분석 리포트
    """
    return {
        "review_id": f"rev_{payload.product_id}_01",
        "rti": 54,
        "signals": {"text": 12, "behavior": 22, "network": 20},
        "reasons": [
            {"title": "반복 문구 밀도 높음", "description": "'품질 완전 대박', '강력추천'이 짧은 문장 안에서 반복되어...", "percentage": "85%"},
            {"title": "구매 이력 확인 불가", "description": "현재 수집된 데이터 기준으로 실제 구매 확인 신호가...", "percentage": "62%"}
        ]
    }

@app.post("/api/internal/ai/products/risk-report", response_model=ProductRiskReportResponse, tags=["AI Reporting"])
async def get_product_risk_report(payload: TriggerRequest):
    """
    [API 5] 상품 위험도 리포트
    """
    return {
        "product_id": payload.product_id,
        "product_name": "SOUNDPRO ANC X7 Pro 블루투스 이어폰 X7 Pro",
        "summary_stat": {
            "total_reviews": 174, 
            "average_rti": 62, 
            "danger_count": 38,
            "warn_count": 54,
            "safe_count": 82
        },
        "trend": [
            {"date": "2026-04-01", "average_rti": 70, "review_count": 10, "safe_count": 5, "warn_count": 3, "danger_count": 2},
            {"date": "2026-04-10", "average_rti": 65, "review_count": 12, "safe_count": 4, "warn_count": 4, "danger_count": 4}
        ],
        "sample_reviews": [
            {
                "review_id": f"rev_{payload.product_id}_sample1", 
                "author": "reviewer_0099", 
                "date": "2026.04.27", 
                "rating": 5, 
                "content": "\"품질 완전 대박. 이런 제품은 처음봐요.\"", 
                "level": "위험", 
                "reasons": [
                    {"code": "REPETITIVE_KEYWORD", "message": "반복 표현"},
                    {"code": "PURCHASE_UNKNOWN", "message": "구매확인 없음"}
                ]
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)