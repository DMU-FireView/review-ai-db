from fastapi import FastAPI, Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta

app = FastAPI(title="Re:view AI Analysis Server (Perfect Alignment Edition)", version="v6.0")

# ==========================================
# 0. Swagger 기본 예시용 샘플 데이터 (동환님 제공)
# ==========================================
from fastapi import FastAPI, Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta

app = FastAPI(title="Re:view AI Analysis Server (Perfect Alignment Edition)", version="v6.0")

# ==========================================
# 0. Swagger 기본 예시용 샘플 데이터 (동환님 제공)
# ==========================================
SAMPLE_REVIEWS = [
    {
      "review_id": "r001", "product_id": "p001", "content": "배송도 빠르고 제품 품질도 괜찮았습니다. 실제로 며칠 써보니 배터리도 오래가고 만족합니다.", "user_id": "user_a", "rating": 5, "review_date": "2026-05-10", "image_count": 2, "quality_score": 0.86
    },
    {
      "review_id": "r002", "product_id": "p001", "content": "진짜 최고예요!!! 완전 강력추천!!! 최고 최고 최고!!!", "user_id": "user_b", "rating": 5, "review_date": "2026-05-10", "image_count": 0, "quality_score": 0.25
    },
    {
      "review_id": "r003", "product_id": "p001", "content": "좋아요", "user_id": "user_c", "rating": 4, "review_date": "2026-05-11", "image_count": 0, "quality_score": 0.1
    },
    {
      "review_id": "r004", "product_id": "p001", "content": "처음에는 괜찮았는데 착용감이 오래 쓰면 조금 불편합니다. 그래도 가격 대비 성능은 나쁘지 않습니다.", "user_id": "user_d", "rating": 3, "review_date": "2026-05-11", "image_count": 1, "quality_score": 0.72
    },
    {
      "review_id": "r005", "product_id": "p001", "content": "완전 대박입니다!!! 친구한테도 추천했고 재구매 의사 있습니다. 포장도 깔끔했어요.", "user_id": "user_e", "rating": 5, "review_date": "2026-05-12", "image_count": 1, "quality_score": 0.64
    }
]

# ==========================================
# 1. Request 스키마 정의 (3개 API 100% 공통)
# ==========================================
class IncomingReview(BaseModel):
    review_id: str
    product_id: str
    content: str
    user_id: str
    rating: int
    review_date: str
    image_count: int = 0
    quality_score: Optional[float] = None

class AnalyzeRequest(BaseModel):
    source: str = Field(default="swagger_test")
    product_name: Optional[str] = Field(default="테스트 블루투스 이어폰")
    reviews: List[IncomingReview]

    model_config = {
        "json_schema_extra": {
            "example": {
                "source": "swagger_test",
                "product_name": "테스트 블루투스 이어폰",
                "reviews": SAMPLE_REVIEWS
            }
        }
    }


# ==========================================
# 2. Response 스키마 정의
# ==========================================
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
    """[수정] Detail API는 오직 이 3개 필드만 반환합니다!! (다른 필드 원천 차단)"""
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


# ==========================================
# 3. [프론트엔드 연동용] 리포트 UI Response 스키마
# ==========================================
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
# 4. API Endpoints
# ==========================================

# --- [파트 1] 3개 API 공통 Request 처리 ---

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["1. AI Analysis (공통 Request)"])
async def analyze_rti_summary(payload: AnalyzeRequest):
    """[API 1] 상품 요약: 리뷰 데이터를 받아 종합 통계를 계산해 반환"""
    return {"products": [{
        "product_id": payload.reviews[0].product_id if payload.reviews else "unknown",
        "average_rti": 85.5, "level": "warn", "review_count": len(payload.reviews),
        "safe_count": 0, "warn_count": len(payload.reviews), "danger_count": 0
    }]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=DetailBatchResponse, tags=["1. AI Analysis (공통 Request)"])
async def analyze_reviews_detail(payload: AnalyzeRequest):
    """
    [API 2] 리뷰 데이터 분석: 
    요청하신 대로 product_id, review_id, url 딱 3개 필드만 리턴합니다.
    """
    results = []
    for r in payload.reviews:
        results.append(SimpleReviewResponseItem(
            product_id=r.product_id,
            review_id=r.review_id,
            url=f"https://smartstore.naver.com/main/products/{r.product_id}" # 생성된 URL 반환
        ))
    return {"results": results}

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["1. AI Analysis (공통 Request)"])
async def get_rti_trend(payload: AnalyzeRequest):
    """
    [API 3] 위험도 추이: 
    요청하신 대로 똑같은 Request를 받지만, 결과는 오늘 기점 30일치 데이터 배열을 반환합니다.
    """
    trend_data = []
    today = datetime.now().date()
    
    # 30일치 통계 루프
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


# --- [파트 2] 프론트엔드 UI 화면 렌더링용 리포트 (조회 전용 GET) ---

@app.get("/api/internal/ai/reviews/{review_id}/report", response_model=ReviewReportResponse, tags=["2. AI Report (프론트엔드 UI 전용)"])
async def get_review_detail_report(review_id: str = Path(...)):
    """
    [API 4 - 신규] 리뷰 상세 분석 리포트 (프론트 이미지 1 렌더링용)
    - 프론트엔드가 화면을 바로 그릴 수 있도록 제공하는 Mock API입니다.
    """
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

@app.get("/api/internal/ai/products/{product_id}/risk-report", response_model=ProductRiskReportResponse, tags=["2. AI Report (프론트엔드 UI 전용)"])
async def get_product_risk_report(product_id: str = Path(...)):
    """
    [API 5 - 신규] 상품 위험도 리포트 (프론트 이미지 2 렌더링용 - 유료 BM)
    - 프론트엔드가 화면을 바로 그릴 수 있도록 제공하는 Mock API입니다.
    """
    return {
        "product_id": product_id,
        "product_name": "SOUNDPRO ANC X7 Pro 블루투스 이어폰 X7 Pro",
        "summary_stat": {
            "total_reviews": 174,
            "average_rti": 62,
            "danger_count": 38,
            "safe_count": 82,
            "key_signal": "반복 표현"
        },
        "trend": [
            {"date": "2026-04-01", "average_rti": 70, "review_count": 10, "safe_count": 5, "warn_count": 3, "danger_count": 2},
            {"date": "2026-04-10", "average_rti": 65, "review_count": 12, "safe_count": 4, "warn_count": 4, "danger_count": 4}
        ],
        "patterns": [
            {"icon_type": "time", "title": "특정 시간대 리뷰 집중", "description": "새벽 1~3시 사이에 유사한 톤의 리뷰가 반복적으로 등록됐어요.", "stat_value": "2.4배", "status": "관찰됨"},
            {"icon_type": "repeat", "title": "반복 표현 증가", "description": "'강력추천', '품질 대박' 등 짧고 유사한 표현이...", "stat_value": "18건", "status": "주의"}
        ],
        "sample_reviews": [
            {
                "review_id": "r001",
                "author": "reviewer_0099",
                "date": "2026.04.27",
                "rating": 5,
                "content": "\"품질 완전 대박. 이런 제품은 처음봐요.\"",
                "level": "위험",
                "tags": ["반복 표현", "구매확인 없음"]
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
# ==========================================
# 1. Request 스키마 정의 (3개 API 100% 공통)
# ==========================================
class IncomingReview(BaseModel):
    review_id: str
    product_id: str
    content: str
    user_id: str
    rating: int
    review_date: str
    image_count: int = 0
    quality_score: Optional[float] = None

class AnalyzeRequest(BaseModel):
    source: str = Field(default="swagger_test")
    product_name: Optional[str] = Field(default="테스트 블루투스 이어폰")
    reviews: List[IncomingReview]

    model_config = {
        "json_schema_extra": {
            "example": {
                "source": "swagger_test",
                "product_name": "테스트 블루투스 이어폰",
                "reviews": SAMPLE_REVIEWS
            }
        }
    }


# ==========================================
# 2. Response 스키마 정의
# ==========================================
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
    """[수정] Detail API는 오직 이 3개 필드만 반환합니다!! (다른 필드 원천 차단)"""
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


# ==========================================
# 3. [프론트엔드 연동용] 리포트 UI Response 스키마
# ==========================================
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
# 4. API Endpoints
# ==========================================

# --- [파트 1] 3개 API 공통 Request 처리 ---

@app.post("/api/internal/ai/products/product-list", response_model=SummaryResponse, tags=["1. AI Analysis (공통 Request)"])
async def analyze_rti_summary(payload: AnalyzeRequest):
    """[API 1] 상품 요약: 리뷰 데이터를 받아 종합 통계를 계산해 반환"""
    return {"products": [{
        "product_id": payload.reviews[0].product_id if payload.reviews else "unknown",
        "average_rti": 85.5, "level": "warn", "review_count": len(payload.reviews),
        "safe_count": 0, "warn_count": len(payload.reviews), "danger_count": 0
    }]}

@app.post("/api/internal/ai/reviews/product-detail", response_model=DetailBatchResponse, tags=["1. AI Analysis (공통 Request)"])
async def analyze_reviews_detail(payload: AnalyzeRequest):
    """
    [API 2] 리뷰 데이터 분석: 
    요청하신 대로 product_id, review_id, url 딱 3개 필드만 리턴합니다.
    """
    results = []
    for r in payload.reviews:
        results.append(SimpleReviewResponseItem(
            product_id=r.product_id,
            review_id=r.review_id,
            url=f"https://smartstore.naver.com/main/products/{r.product_id}" # 생성된 URL 반환
        ))
    return {"results": results}

@app.post("/api/internal/ai/products/rti-trend", response_model=TrendResponse, tags=["1. AI Analysis (공통 Request)"])
async def get_rti_trend(payload: AnalyzeRequest):
    """
    [API 3] 위험도 추이: 
    요청하신 대로 똑같은 Request를 받지만, 결과는 오늘 기점 30일치 데이터 배열을 반환합니다.
    """
    trend_data = []
    today = datetime.now().date()
    
    # 30일치 통계 루프
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


# --- [파트 2] 프론트엔드 UI 화면 렌더링용 리포트 (조회 전용 GET) ---

@app.get("/api/internal/ai/reviews/{review_id}/report", response_model=ReviewReportResponse, tags=["2. AI Report (프론트엔드 UI 전용)"])
async def get_review_detail_report(review_id: str = Path(...)):
    """
    [API 4 - 신규] 리뷰 상세 분석 리포트 (프론트 이미지 1 렌더링용)
    - 프론트엔드가 화면을 바로 그릴 수 있도록 제공하는 Mock API입니다.
    """
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

@app.get("/api/internal/ai/products/{product_id}/risk-report", response_model=ProductRiskReportResponse, tags=["2. AI Report (프론트엔드 UI 전용)"])
async def get_product_risk_report(product_id: str = Path(...)):
    """
    [API 5 - 신규] 상품 위험도 리포트 (프론트 이미지 2 렌더링용 - 유료 BM)
    - 프론트엔드가 화면을 바로 그릴 수 있도록 제공하는 Mock API입니다.
    """
    return {
        "product_id": product_id,
        "product_name": "SOUNDPRO ANC X7 Pro 블루투스 이어폰 X7 Pro",
        "summary_stat": {
            "total_reviews": 174,
            "average_rti": 62,
            "danger_count": 38,
            "safe_count": 82,
            "key_signal": "반복 표현"
        },
        "trend": [
            {"date": "2026-04-01", "average_rti": 70, "review_count": 10, "safe_count": 5, "warn_count": 3, "danger_count": 2},
            {"date": "2026-04-10", "average_rti": 65, "review_count": 12, "safe_count": 4, "warn_count": 4, "danger_count": 4}
        ],
        "patterns": [
            {"icon_type": "time", "title": "특정 시간대 리뷰 집중", "description": "새벽 1~3시 사이에 유사한 톤의 리뷰가 반복적으로 등록됐어요.", "stat_value": "2.4배", "status": "관찰됨"},
            {"icon_type": "repeat", "title": "반복 표현 증가", "description": "'강력추천', '품질 대박' 등 짧고 유사한 표현이...", "stat_value": "18건", "status": "주의"}
        ],
        "sample_reviews": [
            {
                "review_id": "r001",
                "author": "reviewer_0099",
                "date": "2026.04.27",
                "rating": 5,
                "content": "\"품질 완전 대박. 이런 제품은 처음봐요.\"",
                "level": "위험",
                "tags": ["반복 표현", "구매확인 없음"]
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)