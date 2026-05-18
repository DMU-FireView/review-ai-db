from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
from collections import defaultdict
from datetime import datetime

# 기존 프로젝트의 AI 분석 모듈 로드
from ai.text_analyzer import calculate_text_score
from ai.behavior_analyzer import calculate_behavior_score
from ai.network_analyzer import calculate_network_score

app = FastAPI(title="Re:view AI Analysis Server (Clean Payload Edition)", version="v3.0")

# ==========================================
# 1. 🚀 최적화된 Request 스키마 (3개 API 공통 사용)
# ==========================================
class IncomingReview(BaseModel):
    """백엔드/크롤러 모듈에서 AI 분석을 위해 정제해서 넘겨주는 필수 8개 필드"""
    review_id: str
    product_id: str
    content: str
    user_id: str
    rating: int
    review_date: str
    image_count: int = 0
    quality_score: Optional[float] = None

class AnalyzeRequest(BaseModel):
    """3개 API 모두 똑같이 이 가벼운 페이로드를 받습니다."""
    source: str = Field(default="clean_api", description="데이터 출처")
    product_name: Optional[str] = Field(default=None, description="상품명")
    reviews: List[IncomingReview]


# ==========================================
# 2. 내부 분석용 및 응답 스키마
# ==========================================
class ReviewInput(BaseModel):
    """AI 엔진이 실제로 사용하는 데이터 형태 (기본값 자동 세팅용)"""
    source: str
    review_id: str
    product_id: str
    product_name: Optional[str] = None
    content: str
    user_id: str
    rating: int
    review_date: str
    image_count: int
    quality_score: Optional[float] = None
    
    # 💡 AI 서버에서 분석을 위해 강제 세팅하는 기본값 5개
    verified_purchase: str = "unknown"
    repurchase: str = "unknown"
    free_trial: str = "unknown"
    reviews_written_today: int = 1
    similar_review_count: int = 0

class ReasonObject(BaseModel):
    code: str
    message: str

class SignalScores(BaseModel):
    text: int
    behavior: int
    network: int

class InputFeatures(BaseModel):
    image_count: int
    quality_score: Optional[float] = None
    verified_purchase: str
    repurchase: str
    free_trial: str
    reviews_written_today: int
    similar_review_count: int

class AnalysisResult(BaseModel):
    source: str
    review_id: str
    user_id: Optional[str] = None
    product_id: str
    product_name: Optional[str] = None
    rating: int
    review_date: Optional[str] = None
    rti: int
    level: str
    signals: SignalScores
    input_features: InputFeatures
    reasons: List[ReasonObject]

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


# ==========================================
# 3. 데이터 준비 및 핵심 AI 분석 로직
# ==========================================
def prepare_review_input(incoming: IncomingReview, source: str, product_name: Optional[str]) -> ReviewInput:
    """받은 8개 필드 + AI 서버의 5개 기본값을 조합하여 코어 엔진에 전달합니다."""
    return ReviewInput(
        source=source,
        review_id=incoming.review_id,
        product_id=incoming.product_id,
        product_name=product_name,
        content=incoming.content,
        user_id=incoming.user_id,
        rating=incoming.rating,
        review_date=incoming.review_date,
        image_count=incoming.image_count,
        quality_score=incoming.quality_score,
        # 프론트/백에서 보내지 않는 AI 자체 기본값
        verified_purchase="unknown",
        repurchase="unknown",
        free_trial="unknown",
        reviews_written_today=1,
        similar_review_count=0
    )

def get_level(rti: int, reasons: list) -> str:
    if rti < 50: return "danger"
    if rti < 80: return "warn"
    
    penalty_reasons = [r for r in reasons if r.get("code") != "REPURCHASE_SIGNAL"]
    if len(penalty_reasons) > 0: return "warn"
    
    return "safe"

def analyze_single_review(review: ReviewInput) -> AnalysisResult:
    text_score, text_reasons = calculate_text_score(review.content, review.quality_score)
    
    review_dict = review.model_dump()
    behavior_score, behavior_reasons = calculate_behavior_score(review_dict)
    network_score, network_reasons = calculate_network_score(review_dict)

    rti_score = round(text_score * 0.4 + behavior_score * 0.35 + network_score * 0.25)
    all_reasons = text_reasons + behavior_reasons + network_reasons
    level = get_level(rti_score, all_reasons)

    return AnalysisResult(
        source=review.source,
        review_id=review.review_id,
        user_id=review.user_id,
        product_id=review.product_id,
        product_name=review.product_name,
        rating=review.rating,
        review_date=review.review_date,
        rti=rti_score, 
        level=level,
        signals=SignalScores(text=text_score, behavior=behavior_score, network=network_score),
        input_features=InputFeatures(
            image_count=review.image_count,
            quality_score=review.quality_score,
            verified_purchase=review.verified_purchase,
            repurchase=review.repurchase,
            free_trial=review.free_trial,
            reviews_written_today=review.reviews_written_today,
            similar_review_count=review.similar_review_count
        ),
        reasons=[ReasonObject(**r) for r in all_reasons]
    )


# ==========================================
# 4. 결과 집계(Aggregation) 로직
# ==========================================
def extract_product_summary(product_id: str, analyzed_reviews: List[AnalysisResult]) -> ProductSummaryResult:
    review_count = len(analyzed_reviews)
    if review_count == 0:
        return ProductSummaryResult(product_id=product_id, average_rti=0.0, level="safe", review_count=0, safe_count=0, warn_count=0, danger_count=0)

    total_rti = sum(r.rti for r in analyzed_reviews)
    average_rti = round(total_rti / review_count, 2)
    
    safe_count = sum(1 for r in analyzed_reviews if r.level == "safe")
    warn_count = sum(1 for r in analyzed_reviews if r.level == "warn")
    danger_count = sum(1 for r in analyzed_reviews if r.level == "danger")
    
    if danger_count > 0:
        overall_level = "danger"
    elif warn_count > 0:
        overall_level = "warn"
    else:
        overall_level = "safe"
    
    return ProductSummaryResult(
        product_id=product_id, average_rti=average_rti, level=overall_level,
        review_count=review_count, safe_count=safe_count, warn_count=warn_count, danger_count=danger_count
    )

def extract_trend_data(analyzed_reviews: List[AnalysisResult]) -> List[TrendItem]:
    date_groups = defaultdict(lambda: {"total_rti": 0, "count": 0, "safe": 0, "warn": 0, "danger": 0})
    
    for analyzed in analyzed_reviews:
        date_key = analyzed.review_date if analyzed.review_date else datetime.now().strftime("%Y-%m-%d")
        date_groups[date_key]["total_rti"] += analyzed.rti
        date_groups[date_key]["count"] += 1
        date_groups[date_key][analyzed.level] += 1

    trend_items = []
    for date_str, data in sorted(date_groups.items()):
        trend_items.append(TrendItem(
            date=date_str, average_rti=round(data["total_rti"] / data["count"], 2),
            review_count=data["count"], safe_count=data["safe"], warn_count=data["warn"], danger_count=data["danger"]
        ))
    return trend_items


# ==========================================
# 5. API Endpoints (3개 모두 AnalyzeRequest 하나로 완전 통일)
# ==========================================

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["Internal AI API"])
async def analyze_rti_summary(payload: AnalyzeRequest):
    """[API 1] 상품 요약: 8개 필드로 정제된 배열을 받아 요약 통계 리턴"""
    if not payload.reviews: 
        return {"products": []}
    
    mapped_reviews = [prepare_review_input(r, payload.source, payload.product_name) for r in payload.reviews]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    
    product_id = payload.reviews[0].product_id
    summary = extract_product_summary(product_id, analyzed_reviews)
    return {"products": [summary]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=BatchResponse, tags=["Internal AI API"])
async def analyze_reviews_batch(payload: AnalyzeRequest):
    """[API 2] 리뷰 상세 분석: 8개 필드로 정제된 배열을 받아 개별 분석결과 리턴"""
    mapped_reviews = [prepare_review_input(r, payload.source, payload.product_name) for r in payload.reviews]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    return BatchResponse(results=analyzed_reviews)

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["Internal AI API"])
async def analyze_rti_trend(payload: AnalyzeRequest):
    """[API 3] 추이 그래프: 8개 필드로 정제된 배열을 받아 날짜별 추이 리턴"""
    if not payload.reviews: 
        return {"trend": []}
    
    mapped_reviews = [prepare_review_input(r, payload.source, payload.product_name) for r in payload.reviews]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    
    trend_items = extract_trend_data(analyzed_reviews)
    return {"trend": trend_items}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)