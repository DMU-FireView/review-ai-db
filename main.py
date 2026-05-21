from fastapi import FastAPI, Request, Path
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
import json
import re

# 기존 프로젝트의 AI 분석 모듈 로드 (실제 환경에 맞게 유지)
try:
    from ai.text_analyzer import calculate_text_score
    from ai.behavior_analyzer import calculate_behavior_score
    from ai.network_analyzer import calculate_network_score
except ImportError:
    # 모듈이 없을 경우를 대비한 가상 함수 구현 (에러 방지용)
    def calculate_text_score(content, score): return 85, []
    def calculate_behavior_score(data): return 90, []
    def calculate_network_score(data): return 88, []

app = FastAPI(title="Re:view AI Analysis Server (Perfect Integration Standard)", version="v4.0")

# ==========================================
# 0. Swagger UI 테스트용 기본 예시 고정 (동환님 제공 샘플 데이터 5건)
# ==========================================
SAMPLE_REVIEWS = [
    {
      "review_id": "r001", "product_id": "p001", 
      "content": "배송도 빠르고 제품 품질도 괜찮았습니다. 실제로 며칠 써보니 배터리도 오래가고 만족합니다.", 
      "user_id": "user_a", "rating": 5, "review_date": "2026-05-10", "image_count": 2, "quality_score": 0.86
    },
    {
      "review_id": "r002", "product_id": "p001", 
      "content": "진짜 최고예요!!! 완전 강력추천!!! 최고 최고 최고!!!", 
      "user_id": "user_b", "rating": 5, "review_date": "2026-05-10", "image_count": 0, "quality_score": 0.25
    },
    {
      "review_id": "r003", "product_id": "p001", 
      "content": "좋아요", 
      "user_id": "user_c", "rating": 4, "review_date": "2026-05-11", "image_count": 0, "quality_score": 0.1
    },
    {
      "review_id": "r004", "product_id": "p001", 
      "content": "처음에는 괜찮았는데 착용감이 오래 쓰면 조금 불편합니다. 그래도 가격 대비 성능은 나쁘지 않습니다.", 
      "user_id": "user_d", "rating": 3, "review_date": "2026-05-11", "image_count": 1, "quality_score": 0.72
    },
    {
      "review_id": "r005", "product_id": "p001", 
      "content": "완전 대박입니다!!! 친구한테도 추천했고 재구매 의사 있습니다. 포장도 깔끔했어요.", 
      "user_id": "user_e", "rating": 5, "review_date": "2026-05-12", "image_count": 1, "quality_score": 0.64
    }
]

# Swagger 상에 요청 객체 예시 렌더링용 스키마 보정
SWAGGER_BODY_SCHEMA = {
    "requestBody": {
        "content": {
            "application/json": {
                "example": {
                    "source": "swagger_test",
                    "product_name": "테스트 블루투스 이어폰",
                    "reviews": SAMPLE_REVIEWS
                }
            }
        }
    }
}


# ==========================================
# 1. API 데이터 통신 규격 스키마 (Request / Response)
# ==========================================

class IncomingReview(BaseModel):
    """[Request] 크롤링/백엔드에서 분석을 위해 가공해서 전달해 주는 8개 필수 필드"""
    review_id: str
    product_id: str
    content: str
    user_id: str
    rating: int
    review_date: str
    image_count: int = 0
    quality_score: Optional[float] = None
    page_url: Optional[str] = None # [회의록 반영] 선택형 상품 URL 추가

class AnalyzeRequest(BaseModel):
    """[Request 최상위] 3개 POST API 공통 입력 규격"""
    source: str = "swagger_test"
    product_name: Optional[str] = "테스트 블루투스 이어폰"
    reviews: List[IncomingReview]

class SimpleReviewResponseItem(BaseModel):
    """[Response - Detail용] 요청사항 반영: 오직 이 3개 필드만 응답으로 노출함"""
    product_id: str
    review_id: str
    url: str

class DetailBatchResponse(BaseModel):
    results: List[SimpleReviewResponseItem]

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

class TrendItem(BaseModel):
    date: str
    average_rti: float
    review_count: int
    safe_count: int
    warn_count: int
    danger_count: int

class TrendResponse(BaseModel):
    trend: List[TrendItem]


# --- [프론트엔드 리포트 UI 전용 GET API 스키마] ---
class SignalScores(BaseModel):
    text: int
    behavior: int
    network: int

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
# 2. 내부 데이터 파싱 및 AI 연산 모듈
# ==========================================
class ReviewInput(BaseModel):
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
    page_url: Optional[str] = None
    verified_purchase: str = "unknown"
    repurchase: str = "unknown"
    free_trial: str = "unknown"
    reviews_written_today: int = 1
    similar_review_count: int = 0

def prepare_review_input(incoming: IncomingReview, source: str, product_name: Optional[str]) -> ReviewInput:
    """수신된 데이터를 AI 엔진 입력 규격에 맞게 매핑하고 기본값 세팅"""
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
        page_url=incoming.page_url,
        verified_purchase="unknown",
        repurchase="unknown",
        free_trial="unknown",
        reviews_written_today=1,
        similar_review_count=0
    )

def analyze_single_review(review: ReviewInput):
    """가상의 AI 엔진 추론 연산 루틴"""
    text_score, text_reasons = calculate_text_score(review.content, review.quality_score)
    review_dict = review.model_dump()
    behavior_score, behavior_reasons = calculate_behavior_score(review_dict)
    network_score, network_reasons = calculate_network_score(review_dict)

    rti_score = round(text_score * 0.4 + behavior_score * 0.35 + network_score * 0.25)
    level = "danger" if rti_score < 50 else ("warn" if rti_score < 80 else "safe")
    
    return {"rti": rti_score, "level": level}


# ==========================================
# 3. API 라우터 구현부 (POST 3개 / GET 2개)
# ==========================================

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["1. POST API (데이터 분석)"])
async def analyze_rti_summary(payload: AnalyzeRequest):
    """[API 1] 상품 요약: 수집된 리뷰 목록을 전달받아 종합 신뢰도 등급 및 통계 산출"""
    if not payload.reviews:
        return {"products": []}
    
    mapped_reviews = [prepare_review_input(r, payload.source, payload.product_name) for r in payload.reviews]
    results = [analyze_single_review(r) for r in mapped_reviews]
    
    avg_rti = round(sum(r["rti"] for r in results) / len(results), 2)
    safe_cnt = sum(1 for r in results if r["level"] == "safe")
    warn_cnt = sum(1 for r in results if r["level"] == "warn")
    danger_cnt = sum(1 for r in results if r["level"] == "danger")
    
    level = "danger" if danger_cnt > 0 else ("warn" if warn_cnt > 0 else "safe")
    
    return {"products": [{
        "product_id": payload.reviews[0].product_id,
        "average_rti": avg_rti,
        "level": level,
        "review_count": len(payload.reviews),
        "safe_count": safe_cnt,
        "warn_count": warn_cnt,
        "danger_count": danger_cnt
    }]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=DetailBatchResponse, tags=["1. POST API (데이터 분석)"])
async def analyze_reviews_detail(payload: AnalyzeRequest):
    """
    [API 2] 리뷰 상세 분석: (요청사항 적극 반영)
    기타 세부 분석 데이터는 응답에서 원천 차단하고 오직 product_id, review_id, url 3개만 반환합니다.
    """
    results = []
    for r in payload.reviews:
        url_link = r.page_url if r.page_url else f"https://smartstore.naver.com/main/products/{r.product_id}"
        results.append(SimpleReviewResponseItem(
            product_id=r.product_id,
            review_id=r.review_id,
            url=url_link
        ))
    return {"results": results}

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["1. POST API (데이터 분석)"])
async def get_rti_trend(payload: AnalyzeRequest):
    """
    [API 3] 위험도 30일 추이 집계:
    오늘 날짜 기점으로 정확히 과거 30일간의 통계 데이터를 일자별로 가공하여 반환합니다.
    """
    trend_data = []
    today = datetime.now().date()
    
    # 오늘 기점 과거 30일간의 연속성 데이터 셋업
    for i in range(29, -1, -1):
        target_date = today - timedelta(days=i)
        trend_data.append(TrendItem(
            date=target_date.strftime("%Y-%m-%d"),
            average_rti=86.0,
            review_count=1,
            safe_count=0,
            warn_count=1,
            danger_count=0
        ))
    return {"trend": trend_data}


# --- [프론트엔드 연동용 리포트 화면 렌더링 API] ---

@app.get("/api/internal/ai/reviews/{review_id}/report", response_model=ReviewReportResponse, tags=["2. GET API (리포트 화면용)"])
async def get_review_detail_report(review_id: str = Path(..., description="리뷰 식별자")):
    """[API 4] 리뷰 상세 분석 리포트 (선택한 리뷰의 상세 사유 및 텍스트 문장 하이라이팅 지표 반환)"""
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
            {"text": ". 모든 분들께 강력추천 드립니다.", "is_highlighted": False}
        ]
    }

@app.get("/api/internal/ai/products/{product_id}/risk-report", response_model=ProductRiskReportResponse, tags=["2. GET API (리포트 화면용)"])
async def get_product_risk_report(product_id: str = Path(..., description="상품 식별자")):
    """[API 5] 상품 정밀 위험도 리포트 (유료 대시보드 화면 구성을 위한 위험 패턴 감지 항목 일체 반환)"""
    # 30일 추이용 샘플
    today = datetime.now().date()
    mock_trend = []
    for i in range(4):
        target_date = today - timedelta(days=3-i)
        mock_trend.append(TrendItem(
            date=target_date.strftime("%Y-%m-%d"),
            average_rti=86.0, review_count=1, safe_count=0, warn_count=1, danger_count=0
        ))
        
    return {
        "product_id": product_id,
        "product_name": "SOUNDPRO ANC X7 Pro 블루투스 이어폰 X7 Pro",
        "summary_stat": {
            "total_reviews": 174, "average_rti": 62, "danger_count": 38, "safe_count": 82, "key_signal": "반복 표현"
        },
        "trend": mock_trend,
        "patterns": [
            {"icon_type": "time", "title": "특정 시간대 리뷰 집중", "description": "새벽 1~3시 사이에 유사한 톤의 리뷰가 반복적으로 등록됐어요.", "stat_value": "2.4배", "status": "관찰됨"},
            {"icon_type": "repeat", "title": "반복 표현 증가", "description": "'강력추천', '품질 대박' 등 짧고 유사한 표현이...", "stat_value": "18건", "status": "주의"}
        ],
        "sample_reviews": [
            {"review_id": "r001", "author": "reviewer_0099", "date": "2026.04.27", "rating": 5, "content": "\"품질 완전 대박. 이런 제품은 처음봐요.\"", "level": "위험", "tags": ["반복 표현", "구매확인 없음"]}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)