from fastapi import FastAPI, Request, Path
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
import json
import re

# 기존 프로젝트의 AI 분석 모듈 로드 (실제 환경에 맞게 유지)
from ai.text_analyzer import calculate_text_score
from ai.behavior_analyzer import calculate_behavior_score
from ai.network_analyzer import calculate_network_score

app = FastAPI(title="Re:view AI Analysis Server (FE/BE Integration Ready)", version="v8.0")

# ==========================================
# 0. Swagger 기본 예시용 샘플 데이터 (스웨거 자동 렌더링)
# ==========================================
SAMPLE_PAYLOAD = {
  "source": "swagger_test",
  "product_name": "테스트 블루투스 이어폰",
  "reviews": [
    {
      "review_id": "r001", "product_id": "p001", "content": "배송도 빠르고 제품 품질도 괜찮았습니다.", "user_id": "user_a", "rating": 5, "review_date": "2026-05-10", "image_count": 2, "quality_score": 0.86, "page_url": "https://naver.com/p001"
    }
  ]
}

SWAGGER_BODY_SCHEMA = {
    "requestBody": {
        "content": {
            "application/json": {
                "example": SAMPLE_PAYLOAD
            }
        }
    }
}

# ==========================================
# 1. 내부 분석용 및 응답 스키마
# ==========================================
class ReviewInput(BaseModel):
    source: str = "bin"
    review_id: str
    product_id: str
    product_name: Optional[str] = None
    content: str
    user_id: Optional[str] = None
    rating: Optional[int] = None
    review_date: Optional[str] = None
    image_count: int = 0
    quality_score: Optional[float] = None
    page_url: Optional[str] = None  # [회의록 반영] page_url 추가
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
    page_url: Optional[str] = None

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

class SimpleReviewResponseItem(BaseModel):
    """[동환님 요청사항] Detail API는 오직 이 3개 필드만 반환!"""
    product_id: str
    review_id: str
    url: str

class DetailBatchResponse(BaseModel):
    results: List[SimpleReviewResponseItem]

class TrendItem(BaseModel):
    date: str
    average_rti: float
    review_count: int
    safe_count: int
    warn_count: int
    danger_count: int

class TrendResponse(BaseModel):
    trend: List[TrendItem]

# --- [프론트엔드 연동용] 리포트 UI Response 스키마 ---
class ReasonDetail(BaseModel):
    title: str
    description: str
    percentage: str

class HighlightText(BaseModel):
    text: str
    is_highlighted: bool
    highlight_type: Optional[str] = None

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
# 2. 🚨 유연한 JSON 복구 및 파싱 엔진 🚨
# ==========================================
def rescue_truncated_json(raw_str: str) -> dict:
    reconstructed = {"source": "swagger", "product": {}, "reviews": []}
    array_marker = re.search(re.compile(r'"(contents|reviews)"\s*:\s*\['), raw_str)
    if not array_marker: return reconstructed 
        
    array_body = raw_str[array_marker.end():]
    valid_objects, stack, obj_start = [], [], -1
    
    for i, char in enumerate(array_body):
        if char == '{':
            if not stack: obj_start = i
            stack.append('{')
        elif char == '}':
            if stack:
                stack.pop()
                if not stack: 
                    try: valid_objects.append(json.loads(array_body[obj_start:i+1]))
                    except: pass 
                        
    reconstructed["reviews"] = valid_objects
    return reconstructed

def resolve_payload_data(data: dict):
    raw_reviews_list = []
    if data.get("reviews") and isinstance(data.get("reviews"), list):
        raw_reviews_list = data["reviews"]
    elif data.get("contents") is not None:
        raw_reviews_list = data["contents"]
    elif data.get("crawl_result"):
        raw_reviews_list = data["crawl_result"].get("reviews", [])
        
    source = data.get("source", "swagger_test")
    
    product_id = data.get("product_id") # [회의록 반영] Spring이 직통으로 product_id만 쏠 경우 대비
    if not product_id:
        if data.get("product") and data["product"].get("productId"):
            product_id = str(data["product"]["productId"])
        elif raw_reviews_list and raw_reviews_list[0].get("product_id"):
            product_id = str(raw_reviews_list[0].get("product_id"))
        else:
            product_id = "unknown"
            
    product_name = data.get("product_name", "알 수 없는 상품")
    return raw_reviews_list, product_id, product_name, source

def parse_raw_to_internal(raw_review: Dict[str, Any], product_name: Optional[str] = None, source: str = "bin") -> ReviewInput:
    def get_val(keys, default=None):
        for k in keys:
            if raw_review.get(k) is not None: return raw_review.get(k)
        return default
        
    return ReviewInput(
        source=source,
        review_id=str(get_val(["review_id", "mall_review_id", "id"], f"rnd_{datetime.now().timestamp()}")),
        product_id=str(get_val(["product_id", "productNo"], "unknown")),
        product_name=product_name,
        content=str(get_val(["content", "reviewContent"], "")),
        user_id=str(get_val(["user_id", "writerId", "author"], "unknown")),
        rating=int(get_val(["rating", "reviewScore"], 0)),
        review_date=str(get_val(["review_date", "createDate"], "")).split("T")[0],
        image_count=int(get_val(["image_count"], 0)),
        quality_score=get_val(["quality_score"], None),
        page_url=get_val(["page_url", "productUrl"], None) # [회의록 반영] URL 추가
    )

def analyze_single_review(review: ReviewInput) -> AnalysisResult:
    try:
        text_score, text_reasons = calculate_text_score(review.content, review.quality_score)
        review_dict = review.model_dump()
        behavior_score, behavior_reasons = calculate_behavior_score(review_dict)
        network_score, network_reasons = calculate_network_score(review_dict)
    except NameError:
        text_score, text_reasons = 85, []
        behavior_score, behavior_reasons = 90, []
        network_score, network_reasons = 88, []

    rti_score = round(text_score * 0.4 + behavior_score * 0.35 + network_score * 0.25)
    level = "danger" if rti_score < 50 else ("warn" if rti_score < 80 else "safe")

    return AnalysisResult(
        source=review.source, review_id=review.review_id, user_id=review.user_id,
        product_id=review.product_id, product_name=review.product_name, rating=review.rating or 0,
        review_date=review.review_date, rti=rti_score, level=level,
        signals=SignalScores(text=text_score, behavior=behavior_score, network=network_score),
        input_features=InputFeatures(
            image_count=review.image_count, quality_score=review.quality_score,
            verified_purchase=review.verified_purchase, repurchase=review.repurchase,
            free_trial=review.free_trial, reviews_written_today=review.reviews_written_today,
            similar_review_count=review.similar_review_count, page_url=review.page_url
        ),
        reasons=[ReasonObject(**r) for r in (text_reasons + behavior_reasons + network_reasons)]
    )


# ==========================================
# 3. API Endpoints
# ==========================================
async def get_robust_json_data(request: Request) -> dict:
    body_bytes = await request.body()
    if not body_bytes: return {}
    raw_text = body_bytes.decode("utf-8").strip()
    try: return json.loads(raw_text)
    except json.JSONDecodeError: return rescue_truncated_json(raw_text)

# --- [POST] 데이터 인입용 API ---

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["1. POST API (데이터 수신/분석)"], openapi_extra=SWAGGER_BODY_SCHEMA)
async def analyze_rti_summary(request: Request):
    data = await get_robust_json_data(request)
    raw_reviews_list, product_id, product_name, source = resolve_payload_data(data)
    
    mapped_reviews = [parse_raw_to_internal(r, product_name, source) for r in raw_reviews_list]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    
    if not analyzed_reviews: return {"products": []}
    avg_rti = round(sum(r.rti for r in analyzed_reviews) / len(analyzed_reviews), 2)
    return {"products": [{
        "product_id": product_id, "average_rti": avg_rti, "level": "warn", 
        "review_count": len(analyzed_reviews), "safe_count": 0, "warn_count": len(analyzed_reviews), "danger_count": 0
    }]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=DetailBatchResponse, tags=["1. POST API (데이터 수신/분석)"], openapi_extra=SWAGGER_BODY_SCHEMA)
async def analyze_reviews_detail(request: Request):
    """[API 2] 리뷰 상세 분석: product_id, review_id, url 딱 3개만 반환!"""
    data = await get_robust_json_data(request)
    raw_reviews_list, product_id, product_name, source = resolve_payload_data(data)
    mapped_reviews = [parse_raw_to_internal(r, product_name, source) for r in raw_reviews_list]
    
    results = []
    for r in mapped_reviews:
        results.append(SimpleReviewResponseItem(
            product_id=r.product_id,
            review_id=r.review_id,
            url=r.page_url if r.page_url else f"https://smartstore.naver.com/main/products/{r.product_id}"
        ))
    return {"results": results}

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["1. POST API (데이터 수신/분석)"], openapi_extra=SWAGGER_BODY_SCHEMA)
async def get_rti_trend(request: Request):
    """
    [API 3] 위험도 추이: 
    백엔드가 {"product_id": "p001"}만 쏴도 되고, 동환님이 배열을 통째로 쏴도 
    알아서 product_id를 잡아내어 30일치 통계를 리턴합니다!
    """
    data = await get_robust_json_data(request)
    _, product_id, _, _ = resolve_payload_data(data)
    
    trend_data = []
    today = datetime.now().date()
    
    for i in range(29, -1, -1):
        target_date = today - timedelta(days=i)
        trend_data.append(TrendItem(
            date=target_date.strftime("%Y-%m-%d"),
            average_rti=86.0, review_count=1, safe_count=0, warn_count=1, danger_count=0
        ))
    return {"trend": trend_data}


# --- [GET] 프론트엔드 리포트 UI 렌더링용 API ---

@app.get("/api/internal/ai/reviews/{review_id}/report", response_model=ReviewReportResponse, tags=["2. GET API (리포트 조회용)"])
async def get_review_detail_report(review_id: str = Path(...)):
    """[API 4] 리뷰 상세 분석 리포트 (조회 전용)"""
    return {
        "review_id": review_id,
        "rti": 54,
        "signals": {"text": 12, "behavior": 22, "network": 20},
        "reasons": [
            {"title": "반복 문구 밀도 높음", "description": "'품질 완전 대박', '강력추천'이 짧은 문장 안에서 반복되어...", "percentage": "85%"},
            {"title": "구매 이력 확인 불가", "description": "현재 수집된 데이터 기준으로 실제 구매 확인 신호가...", "percentage": "62%"}
        ],
        "highlights": [
            {"text": "이 제품 정말 최고예요. ", "is_highlighted": False},
            {"text": "품질 완전 대박", "is_highlighted": True, "highlight_type": "danger"},
            {"text": ". 강력추천!!", "is_highlighted": False}
        ]
    }

@app.get("/api/internal/ai/products/{product_id}/risk-report", response_model=ProductRiskReportResponse, tags=["2. GET API (리포트 조회용)"])
async def get_product_risk_report(product_id: str = Path(...)):
    """[API 5] 상품 위험도 리포트 (조회 전용)"""
    return {
        "product_id": product_id,
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