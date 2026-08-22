"""내부 AI API와 분석 서비스가 공유하는 요청·응답 DTO를 정의한다."""

from typing import Any

from pydantic import BaseModel, Field


class TriggerRequest(BaseModel):
    product_id: str = Field(..., description="조회할 상품의 고유 식별자 (상품ID)")
    url: str | None = Field(None, description="상품 URL (page_url, product_url 호환)")
    page_url: str | None = None
    product_url: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "53530143052",
                "url": "https://smartstore.naver.com/main/products/11590446932",
            }
        }
    }


class ReviewInput(BaseModel):
    review_id: str
    product_id: str
    user_id: str
    content: str
    review_date: str
    rating: int = 5
    image_count: int = 0
    quality_score: float | None = None
    verified_purchase: Any = "unknown"
    repurchase: Any = "unknown"
    free_trial: Any = "unknown"
    reviews_written_today: int = 1
    similar_review_count: int = 0


class IncomingReview(BaseModel):
    """정규화 스크립트에서 분석 서비스로 전달하는 호환 입력 모델."""

    review_id: str
    product_id: str | None = None
    product_url: str = ""
    user_id: str
    content: str
    review_date: str
    rating: int = 5
    image_count: int = 0
    quality_score: float | None = None
    verified_purchase: Any = "unknown"
    repurchase: Any = "unknown"
    free_trial: Any = "unknown"
    reviews_written_today: int = 1
    similar_review_count: int = 0


class SignalScores(BaseModel):
    text: int
    behavior: int
    network: int


class ReasonObject(BaseModel):
    code: str
    message: str


class InputFeatures(BaseModel):
    image_count: int
    quality_score: float | None = None
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
    products: list[ProductSummaryResult]


class AnalysisResult(BaseModel):
    review_id: str
    content: str
    author: str
    date: str
    rti: int
    level: str
    signals: SignalScores
    input_features: InputFeatures
    reasons: list[ReasonObject]


class BatchResponse(BaseModel):
    results: list[AnalysisResult]


class TrendItem(BaseModel):
    date: str
    average_rti: float
    review_count: int
    safe_count: int
    warn_count: int
    danger_count: int


class TrendResponse(BaseModel):
    trend: list[TrendItem]


class ReasonDetail(BaseModel):
    title: str
    description: str


class ReviewReportResponse(BaseModel):
    review_id: str
    rti: int
    signals: SignalScores
    reasons: list[ReasonDetail]


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
    reasons: list[ReasonObject]


class ProductRiskReportResponse(BaseModel):
    product_id: str
    product_name: str
    summary_stat: SummaryStat
    trend: list[TrendItem]
    sample_reviews: list[SampleReview]
