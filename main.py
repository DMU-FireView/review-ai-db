from fastapi import FastAPI, Query, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from collections import defaultdict
from datetime import datetime
import json
import re

# 기존 프로젝트의 AI 분석 모듈 로드
from ai.text_analyzer import calculate_text_score
from ai.behavior_analyzer import calculate_behavior_score
from ai.network_analyzer import calculate_network_score

app = FastAPI(title="Re:view AI Analysis Server (Robust Rescue Edition)", version="v0.3")

# ==========================================
# 1. 문서화용 Pydantic 스키마 정의 (Swagger 노출용)
# ==========================================
class RawCrawlPayload(BaseModel):
    source: str = Field(default="bin")
    query: Optional[str] = None
    product: Dict[str, Any] = Field(default_factory=dict)
    crawl_result: Dict[str, Any] = Field(default_factory=dict)
    contents: Optional[List[Dict[str, Any]]] = Field(default=None)

# ==========================================
# 2. 내부 분석용 및 응답 스키마
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
# 3. 🚨 [핵심 추가] 짤린 JSON 자동 구조 복구 엔진 🚨
# ==========================================
def rescue_truncated_json(raw_str: str) -> dict:
    """
    텍스트 복사 짤림 등으로 손상된 JSON 문자열에서 
    정상 완료된 리뷰 객체들만 스택 분석으로 안전하게 구출해 냅니다.
    """
    reconstructed = {
        "source": "bin", "query": None, "product": {},
        "crawl_result": {"reviews": []}, "contents": None
    }
    
    # 1. 정규식을 이용하여 문자열 전반에서 메타데이터 복원 구출
    source_match = re.search(re.compile(r'"source"\s*:\s*"([^"]+)"'), raw_str)
    if source_match: reconstructed["source"] = source_match.group(1)
    
    query_match = re.search(re.compile(r'"query"\s*:\s*"([^"]+)"'), raw_str)
    if query_match: reconstructed["query"] = query_match.group(1)
    
    prod_id_match = re.search(re.compile(r'"(productId|productNo)"\s*:\s*"([^"]+)"'), raw_str)
    if prod_id_match: reconstructed["product"]["productId"] = prod_id_match.group(2)
    
    prod_title_match = re.search(re.compile(r'"(title|productName)"\s*:\s*"([^"]+)"'), raw_str)
    if prod_title_match: reconstructed["product"]["title"] = prod_title_match.group(2)

    # 2. 하연님 포맷(contents)인지 빈님 포맷(reviews)인지 배열 마커 확인
    array_marker = re.search(re.compile(r'"(contents|reviews)"\s*:\s*\['), raw_str)
    if not array_marker:
        return reconstructed # 배열이 시작되기도 전에 짤렸으면 빈 값 리턴
        
    is_contents_format = array_marker.group(1) == "contents"
    array_body = raw_str[array_marker.end():]
    
    # 3. 괄호 쌍 매칭 스택으로 정상 완성된 개별 딕셔너리 객체만 구출
    valid_objects = []
    stack = []
    obj_start = -1
    
    for i, char in enumerate(array_body):
        if char == '{':
            if not stack:
                obj_start = i
            stack.append('{')
        elif char == '}':
            if stack:
                stack.pop()
                if not stack: # 한 리뷰 오브젝트가 완벽하게 닫힘!
                    obj_str = array_body[obj_start:i+1]
                    try:
                        valid_objects.append(json.loads(obj_str))
                    except:
                        pass # 불완전 조각 폐기
                        
    # 4. 정규 규격으로 안착
    if is_contents_format:
        reconstructed["contents"] = valid_objects
        if reconstructed["source"] == "bin": reconstructed["source"] = "naver"
    else:
        reconstructed["crawl_result"]["reviews"] = valid_objects
        
    return reconstructed


# ==========================================
# 4. 공통 데이터 프로세싱 파트
# ==========================================
def get_compatible_field(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for k in keys:
        val = d.get(k)
        if val is not None and val != "": return val
    return default

def resolve_payload_data(data: dict):
    if data.get("contents") is not None:
        raw_reviews_list = data["contents"]
        source = data.get("source", "naver")
    else:
        crawl_res = data.get("crawl_result", {})
        raw_reviews_list = crawl_res.get("reviews", []) if isinstance(crawl_res, dict) else []
        source = data.get("source", "bin")

    product_obj = data.get("product", {})
    product_id = "unknown"
    if product_obj and product_obj.get("productId"):
        product_id = str(product_obj.get("productId"))
    elif raw_reviews_list:
        product_id = str(get_compatible_field(raw_reviews_list[0], ["productNo", "product_id"], "unknown"))

    product_name = None
    if product_obj and product_obj.get("title"):
        product_name = product_obj.get("title")
    elif raw_reviews_list:
        product_name = get_compatible_field(raw_reviews_list[0], ["productName", "product_name"])

    return raw_reviews_list, product_id, product_name, source

def parse_raw_to_internal(raw_review: Dict[str, Any], product_name: Optional[str] = None, source: str = "bin") -> ReviewInput:
    review_id = str(get_compatible_field(raw_review, ["mall_review_id", "id", "review_id"], ""))
    product_id = str(get_compatible_field(raw_review, ["productNo", "product_id"], ""))
    content = str(get_compatible_field(raw_review, ["reviewContent", "content"], ""))
    user_id = str(get_compatible_field(raw_review, ["writerId", "author", "user_id"], "unknown"))
    
    rating_val = get_compatible_field(raw_review, ["reviewScore", "rating"])
    rating = int(rating_val) if rating_val is not None else 0
    
    raw_date = get_compatible_field(raw_review, ["createDate", "review_date"])
    review_date = str(raw_date).split("T")[0] if raw_date and "T" in str(raw_date) else (str(raw_date) if raw_date else None)
        
    image_count = int(raw_review.get("image_count", 0) or 0)
    if not image_count and "reviewAttaches" in raw_review:
        image_count = len(raw_review["reviewAttaches"] or [])
        
    quality_score = float(raw_review.get("quality_score")) if raw_review.get("quality_score") is not None else None
    
    free_trial_val = get_compatible_field(raw_review, ["freeTrial", "free_trial"])
    free_trial = "true" if isinstance(free_trial_val, bool) and free_trial_val else ("false" if isinstance(free_trial_val, bool) else str(free_trial_val or "unknown"))
        
    repurchase_val = get_compatible_field(raw_review, ["repurchase"])
    repurchase = "true" if isinstance(repurchase_val, bool) and repurchase_val else ("false" if isinstance(repurchase_val, bool) else str(repurchase_val or "unknown"))

    return ReviewInput(
        source=source, review_id=review_id, product_id=product_id, product_name=product_name,
        content=content, user_id=user_id, rating=rating, review_date=review_date, image_count=image_count,
        quality_score=quality_score, verified_purchase=str(raw_review.get("verified_purchase", "unknown")),
        repurchase=repurchase, free_trial=free_trial,
        reviews_written_today=int(raw_review.get("reviews_written_today", 1) or 1),
        similar_review_count=int(raw_review.get("similar_review_count", 0) or 0)
    )

def get_level(rti: int, reasons: list) -> str:
    if rti < 50: return "danger"
    if rti < 80: return "warn"
    if len([r for r in reasons if r.get("code") != "REPURCHASE_SIGNAL"]) > 0: return "warn"
    return "safe"

def analyze_single_review(review: ReviewInput) -> AnalysisResult:
    text_score, text_reasons = calculate_text_score(review.content, review.quality_score)
    review_dict = review.model_dump()
    behavior_score, behavior_reasons = calculate_behavior_score(review_dict)
    network_score, network_reasons = calculate_network_score(review_dict)

    rti_score = round(text_score * 0.4 + behavior_score * 0.35 + network_score * 0.25)
    all_reasons = text_reasons + behavior_reasons + network_reasons

    return AnalysisResult(
        source=review.source, review_id=review.review_id, user_id=review.user_id,
        product_id=review.product_id, product_name=review.product_name, rating=review.rating or 0,
        review_date=review.review_date, rti=rti_score, level=get_level(rti_score, all_reasons),
        signals=SignalScores(text=text_score, behavior=behavior_score, network=network_score),
        input_features=InputFeatures(
            image_count=review.image_count, quality_score=review.quality_score,
            verified_purchase=review.verified_purchase, repurchase=review.repurchase,
            free_trial=review.free_trial, reviews_written_today=review.reviews_written_today,
            similar_review_count=review.similar_review_count
        ),
        reasons=[ReasonObject(**r) for r in all_reasons]
    )

def extract_product_summary(product_id: str, analyzed_reviews: List[AnalysisResult]) -> ProductSummaryResult:
    review_count = len(analyzed_reviews)
    if review_count == 0:
        return ProductSummaryResult(product_id=product_id, average_rti=0.0, level="safe", review_count=0, safe_count=0, warn_count=0, danger_count=0)
    
    average_rti = round(sum(r.rti for r in analyzed_reviews) / review_count, 2)
    safe_count = sum(1 for r in analyzed_reviews if r.level == "safe")
    warn_count = sum(1 for r in analyzed_reviews if r.level == "warn")
    danger_count = sum(1 for r in analyzed_reviews if r.level == "danger")
    
    overall_level = "danger" if danger_count > 0 else ("warn" if warn_count > 0 else "safe")
    return ProductSummaryResult(product_id=product_id, average_rti=average_rti, level=overall_level, review_count=review_count, safe_count=safe_count, warn_count=warn_count, danger_count=danger_count)

def extract_trend_data(raw_reviews: List[Dict[str, Any]], analyzed_reviews: List[AnalysisResult]) -> List[TrendItem]:
    date_groups = defaultdict(lambda: {"total_rti": 0, "count": 0, "safe": 0, "warn": 0, "danger": 0})
    for raw, analyzed in zip(raw_reviews, analyzed_reviews):
        date_key = analyzed.review_date if analyzed.review_date else datetime.now().strftime("%Y-%m-%d")
        date_groups[date_key]["total_rti"] += analyzed.rti
        date_groups[date_key]["count"] += 1
        date_groups[date_key][analyzed.level] += 1
    return [TrendItem(date=d, average_rti=round(v["total_rti"]/v["count"], 2), review_count=v["count"], safe_count=v["safe"], warn_count=v["warn"], danger_count=v["danger"]) for d, v in sorted(date_groups.items())]


# ==========================================
# 5. [초강력 업그레이드] API Endpoints (422 완전 방어 가드 장착)
# ==========================================
async def get_robust_json_data(request: Request) -> dict:
    """엔드포인트 공용 텍스트 스트림 수신 및 자동 복구 래퍼"""
    body_bytes = await request.body()
    raw_text = body_bytes.decode("utf-8").strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # 문법 에러 감지 시 즉시 복구 엔진 가동!!
        return rescue_truncated_json(raw_text)

# Swagger 연동 문서 강제 주입 규격 정의
SWAGGER_BODY_SCHEMA = {"requestBody": {"content": {"application/json": {"schema": RawCrawlPayload.model_json_schema()}}}}

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["Internal AI API"], openapi_extra=SWAGGER_BODY_SCHEMA)
async def analyze_rti_summary(request: Request):
    data = await get_robust_json_data(request)
    raw_reviews_list, product_id, product_name, source = resolve_payload_data(data)
    mapped_reviews = [parse_raw_to_internal(r, product_name, source) for r in raw_reviews_list]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    return {"products": [extract_product_summary(product_id, analyzed_reviews)]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=BatchResponse, tags=["Internal AI API"], openapi_extra=SWAGGER_BODY_SCHEMA)
async def analyze_reviews_batch(request: Request):
    data = await get_robust_json_data(request)
    raw_reviews_list, product_id, product_name, source = resolve_payload_data(data)
    mapped_reviews = [parse_raw_to_internal(r, product_name, source) for r in raw_reviews_list]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    return BatchResponse(results=analyzed_reviews)

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["Internal AI API"], openapi_extra=SWAGGER_BODY_SCHEMA)
async def analyze_rti_trend(request: Request):
    data = await get_robust_json_data(request)
    raw_reviews_list, product_id, product_name, source = resolve_payload_data(data)
    if not raw_reviews_list: return {"trend": []}
    mapped_reviews = [parse_raw_to_internal(r, product_name, source) for r in raw_reviews_list]
    analyzed_reviews = [analyze_single_review(r) for r in mapped_reviews]
    return {"trend": extract_trend_data(raw_reviews_list, analyzed_reviews)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)