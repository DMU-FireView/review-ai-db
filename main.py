from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta

# 기존 프로젝트의 AI 분석 모듈 로드 (실제 환경에 맞게 유지)
try:
    from ai.text_analyzer import calculate_text_score
    from ai.behavior_analyzer import calculate_behavior_score
    from ai.network_analyzer import calculate_network_score
except ImportError:
    def calculate_text_score(content, score): return 85, []
    def calculate_behavior_score(data): return 90, []
    def calculate_network_score(data): return 88, []

app = FastAPI(title="Re:view AI Analysis Server (Trigger Edition)", version="v9.1")


# ==========================================
# 1. 🚀 Request 스키마 (초경량 트리거 규격)
# 백엔드는 이제 리뷰를 보내지 않습니다. 식별자만 보냅니다.
# ==========================================
class TriggerRequest(BaseModel):
    product_id: str = Field(..., description="조회할 상품의 고유 ID")
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
# 2. Response 스키마 (PDF 명세서 및 UI 화면 완벽 동기화)
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

class HighlightText(BaseModel):
    """UI 화면의 '문장 근거 하이라이트'를 위해 추가된 모델"""
    text: str
    is_highlighted: bool
    highlight_type: Optional[str] = None

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
    highlights: List[HighlightText] # UI 렌더링용 하이라이트

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


# --- [API 4 & 5: 리포트 UI 전용 응답 모델 추가 복구] ---
class ReasonDetail(BaseModel):
    title: str
    description: str
    percentage: str

class ReviewReportResponse(BaseModel):
    review_id: str
    rti: int
    signals: SignalScores
    reasons: List[ReasonDetail]
    highlights: List[HighlightText]

class RiskPattern(BaseModel):
    icon_type: str
    title: str
    description: str
    stat_value: str
    status: str 

class SampleReview(BaseModel):
    review_id: str
    author: str
    date: str
    rating: int
    content: str
    level: str
    tags: List[str]

class ProductRiskReportResponse(BaseModel):
    product_id: str
    product_name: str
    summary_stat: dict
    trend: List[TrendItem]
    patterns: List[RiskPattern]
    sample_reviews: List[SampleReview]


# ==========================================
# 3. 데이터 Mocking 로직 (AI 서버가 자체적으로 데이터를 가져온다고 가정)
# ==========================================
def mock_fetch_reviews_from_db_or_crawler(product_id: str, url: str):
    """
    백엔드가 product_id만 주면, AI 서버가 내부 DB나 크롤러를 통해 
    분석할 리뷰 데이터를 가져오는 (가상의) 함수입니다.
    """
    return [
        {
            "review_id": "r001", "content": "굉장히 작고 귀엽고 가볍습니다!! 너무 행복하네요 대박 대박", 
            "quality_score": 0.76, "image_count": 3
        },
        {
            "review_id": "r002", "content": "진짜 최고예요!!! 완전 강력추천!!! 최고 최고 최고!!!", 
            "quality_score": 0.25, "image_count": 0
        }
    ]


# ==========================================
# 4. API Endpoints (5개 POST API 완벽 통일)
# ==========================================

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["AI Analysis"])
async def analyze_rti_summary(payload: TriggerRequest):
    """
    [API 1] 상품 요약: product_id를 받아 상품 단위 통계를 반환합니다. (PDF 규격 일치)
    """
    # 실제로는 payload.product_id 로 크롤러/DB 호출
    target_url = payload.url or payload.page_url or payload.product_url
    
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
    [API 2] 리뷰 상세 분석: product_id를 받아 개별 리뷰 분석 결과를 반환합니다. (PDF + UI 규격)
    """
    # 실제로는 payload.product_id 로 크롤러/DB 호출
    reviews = mock_fetch_reviews_from_db_or_crawler(payload.product_id, payload.url)
    
    results = []
    for r in reviews:
        # UI에 그리기 위한 필수 값들 매핑 (PDF 기준 + UI 기준)
        results.append(AnalysisResult(
            review_id=r["review_id"],
            rti=54 if r["review_id"] == "r002" else 88,
            level="danger" if r["review_id"] == "r002" else "safe",
            signals=SignalScores(text=12, behavior=22, network=20),
            input_features=InputFeatures(image_count=r["image_count"], quality_score=r["quality_score"]),
            reasons=[
                ReasonObject(code="REPETITIVE_KEYWORD", message="반복 문구 밀도 높음"),
                ReasonObject(code="PURCHASE_UNKNOWN", message="구매 이력 확인 불가")
            ],
            highlights=[
                HighlightText(text="이 제품 정말 최고예요. ", is_highlighted=False),
                HighlightText(text="완전 강력추천", is_highlighted=True, highlight_type="danger"),
                HighlightText(text="!!", is_highlighted=False)
            ]
        ))
        
    return {"results": results}

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["AI Analysis"])
async def get_rti_trend(payload: TriggerRequest):
    """
    [API 3] 위험도 추이: product_id를 받아 30일치 통계를 배열로 리턴합니다. (PDF 규격 일치)
    """
    trend_data = []
    today = datetime.now().date()
    
    # 30일치 데이터 Mock 생성
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
    [API 4 - 신규] 리뷰 상세 분석 리포트 (GET -> POST 변경)
    모든 API와 동일하게 TriggerRequest를 받으며 UI 테스트용 Mock 데이터를 반환합니다.
    """
    return {
        "review_id": "r001",
        "rti": 54,
        "signals": {"text": 12, "behavior": 22, "network": 20},
        "reasons": [
            {"title": "반복 문구 밀도 높음", "description": "'품질 완전 대박', '강력추천'이 짧은 문장 안에서 반복되어...", "percentage": "85%"},
            {"title": "구매 이력 확인 불가", "description": "현재 수집된 데이터 기준으로 실제 구매 확인 신호가...", "percentage": "62%"}
        ],
        "highlights": [
            {"text": "이 제품 정말 최고예요. ", "is_highlighted": False},
            {"text": "완전 강력추천", "is_highlighted": True, "highlight_type": "danger"},
            {"text": "!!", "is_highlighted": False}
        ]
    }

@app.post("/api/internal/ai/products/risk-report", response_model=ProductRiskReportResponse, tags=["AI Reporting"])
async def get_product_risk_report(payload: TriggerRequest):
    """
    [API 5 - 신규] 상품 위험도 리포트 (GET -> POST 변경)
    모든 API와 동일하게 TriggerRequest를 받으며 대시보드 렌더링용 데이터를 반환합니다.
    """
    return {
        "product_id": payload.product_id,
        "product_name": "SOUNDPRO ANC X7 Pro 블루투스 이어폰 X7 Pro",
        "summary_stat": {
            "total_reviews": 174, "average_rti": 62, "danger_count": 38, "safe_count": 82, "key_signal": "반복 표현"
        },
        "trend": [
            {"date": "2026-04-01", "average_rti": 70, "review_count": 10, "safe_count": 5, "warn_count": 3, "danger_count": 2},
            {"date": "2026-04-10", "average_rti": 65, "review_count": 12, "safe_count": 4, "warn_count": 4, "danger_count": 4}
        ],
        "patterns": [
            {"icon_type": "time", "title": "특정 시간대 리뷰 집중", "description": "새벽 1~3시 사이에 유사한 톤의 리뷰가 반복적으로 등록됐어요.", "stat_value": "2.4배", "status": "관찰됨"}
        ],
        "sample_reviews": [
            {"review_id": "r001", "author": "reviewer_0099", "date": "2026.04.27", "rating": 5, "content": "\"품질 완전 대박. 이런 제품은 처음봐요.\"", "level": "위험", "tags": ["반복 표현", "구매확인 없음"]}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)