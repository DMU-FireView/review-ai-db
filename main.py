from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from collections import defaultdict
from datetime import datetime

# 기존 프로젝트의 AI 분석 모듈 로드
from ai.text_analyzer import calculate_text_score
from ai.behavior_analyzer import calculate_behavior_score
from ai.network_analyzer import calculate_network_score

app = FastAPI(title="Re:view AI Analysis Server", version="v0.2")

# ==========================================
# 1. 크롤링 원본(Raw) 입력 스키마 (유연성 극대화)
# ==========================================
class RawCrawlPayload(BaseModel):
    """
    크롤링된 생데이터를 통째로 받습니다. 
    422 에러 방지를 위해 product와 crawl_result를 유연한 Dict 타입으로 받습니다.
    """
    query: Optional[str] = None
    product: Dict[str, Any] = Field(default_factory=dict)
    crawl_result: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "query": "무선이어폰",
                "product": {
                    "productId": "53530143052",
                    "title": "로랜텍 커널형 버즈 무선 블루투스 이어폰 RSM-R510"
                },
                "crawl_result": {
                    "total_count": 1,
                    "reviews": [
                        {
                            "review_id": "4879548868-ncp_1nuc11_01-11590446932",
                            "product_id": "53530143052",
                            "rating": 5,
                            "content": "굉장히 작고 귀엽고 가볍습니다!! 너무 행복하네요 대박 대박",
                            "author": "bouo****",
                            "review_date": "2026-01-07",
                            "image_count": 3,
                            "quality_score": 0.761338
                        }
                    ]
                }
            }
        }


# ==========================================
# 2. 내부 분석용 스키마 및 응답 스키마
# ==========================================
class ReviewInput(BaseModel):
    """AI 엔진이 실제로 사용하는 정제된 내부 데이터 형태"""
    review_id: str
    product_id: str
    content: str
    user_id: Optional[str] = None
    rating: Optional[int] = None
    review_date: Optional[str] = None
    image_count: int = 0
    quality_score: Optional[float] = None
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

class AnalysisResult(BaseModel):
    review_id: str
    product_id: str
    rti: int
    level: str
    signals: SignalScores
    reasons: List[ReasonObject]

class ProductSummaryResult(BaseModel):
    product_id: str
    average_rti: float
    level: str
    review_count: int
    safe_count: int
    warn_count: int
    danger_count: int

# 새로 추가된 명확한 응답 스키마 (additionalProp 제거용)
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

# 새로 추가된 명확한 응답 스키마 (additionalProp 제거용)
class TrendResponse(BaseModel):
    trend: List[TrendItem]


# ==========================================
# 3. 데이터 파싱 및 핵심 AI 분석 로직
# ==========================================
def parse_raw_to_internal(raw_review: Dict[str, Any]) -> ReviewInput:
    """크롤링된 생데이터 딕셔너리에서 에러 없이 안전하게(.get) 필요한 값만 추출합니다."""
    return ReviewInput(
        review_id=str(raw_review.get("review_id", "")),
        product_id=str(raw_review.get("product_id", "")),
        content=str(raw_review.get("content", "")),
        user_id=str(raw_review.get("author", "unknown")),
        
        # 숫자형 데이터들은 None 방어 처리
        rating=int(raw_review.get("rating", 0) or 0),
        review_date=str(raw_review.get("review_date", "")),
        image_count=int(raw_review.get("image_count", 0) or 0),
        quality_score=float(raw_review.get("quality_score")) if raw_review.get("quality_score") is not None else None,
        
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
        review_id=review.review_id, 
        product_id=review.product_id,
        rti=rti_score, 
        level=level,
        signals=SignalScores(text=text_score, behavior=behavior_score, network=network_score),
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
    
    overall_level = "safe" if average_rti >= 80 else ("warn" if average_rti >= 50 else "danger")
    
    return ProductSummaryResult(
        product_id=product_id, average_rti=average_rti, level=overall_level,
        review_count=review_count, safe_count=safe_count, warn_count=warn_count, danger_count=danger_count
    )

def extract_trend_data(raw_reviews: List[Dict[str, Any]], analyzed_reviews: List[AnalysisResult]) -> List[TrendItem]:
    date_groups = defaultdict(lambda: {"total_rti": 0, "count": 0, "safe": 0, "warn": 0, "danger": 0})
    
    for raw, analyzed in zip(raw_reviews, analyzed_reviews):
        date_key = raw.get("review_date") or datetime.now().strftime("%Y-%m-%d")
        
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
# 5. API Endpoints
# ==========================================

@app.post("/api/internal/ai/products/rti-summary", response_model=SummaryResponse, tags=["Internal AI API"])
async def analyze_rti_summary(payload: RawCrawlPayload):
    raw_reviews_list = payload.crawl_result.get("reviews", [])
    product_id = str(payload.product.get("productId", "unknown"))

    mapped_reviews = [parse_raw_to_internal(r) for r in raw_reviews_list]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    
    summary = extract_product_summary(product_id, analyzed_reviews)
    return {"products": [summary]}


@app.post("/api/internal/ai/reviews/analyze-batch", response_model=BatchResponse, tags=["Internal AI API"])
async def analyze_reviews_batch(payload: RawCrawlPayload):
    raw_reviews_list = payload.crawl_result.get("reviews", [])
    
    mapped_reviews = [parse_raw_to_internal(r) for r in raw_reviews_list]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    
    return BatchResponse(results=analyzed_reviews)


@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["Internal AI API"])
async def analyze_rti_trend(payload: RawCrawlPayload):
    raw_reviews_list = payload.crawl_result.get("reviews", [])

    if not raw_reviews_list:
        return {"trend": []}

    mapped_reviews = [parse_raw_to_internal(r) for r in raw_reviews_list]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    
    trend_items = extract_trend_data(raw_reviews_list, analyzed_reviews)
        
    return {"trend": trend_items}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)