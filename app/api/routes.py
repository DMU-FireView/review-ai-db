"""Spring Boot 백엔드가 호출하는 내부 AI API 엔드포인트를 제공한다."""

from fastapi import APIRouter

from app.api.schemas import (
    BatchResponse,
    ProductRiskReportResponse,
    ReviewReportResponse,
    SummaryResponse,
    TrendResponse,
    TriggerRequest,
)
from app.repositories.products import get_product_name, resolve_product_id
from app.repositories.reviews import find_by_product_id
from app.services.analysis import analyze_reviews
from app.services.product import (
    build_review_report,
    build_risk_report,
    build_summary,
    build_trend,
)


router = APIRouter(prefix="/api/internal/ai")


def load_product_analysis(payload: TriggerRequest):
    product_id = resolve_product_id(payload)
    reviews = find_by_product_id(product_id)
    return product_id, reviews, analyze_reviews(reviews)


@router.post("/products/product-list", response_model=SummaryResponse, tags=["AI Analysis"])
async def analyze_rti_summary(payload: TriggerRequest):
    product_id, _, results = load_product_analysis(payload)
    summary = build_summary(product_id, results)
    return SummaryResponse(products=[summary] if summary else [])


@router.post("/reviews/product-detail", response_model=BatchResponse, tags=["AI Analysis"])
async def analyze_reviews_detail(payload: TriggerRequest):
    _, _, results = load_product_analysis(payload)
    return BatchResponse(results=results)


@router.post("/products/rti-trend", response_model=TrendResponse, tags=["AI Analysis"])
async def get_rti_trend(payload: TriggerRequest):
    _, reviews, results = load_product_analysis(payload)
    return TrendResponse(trend=build_trend(results, reviews))


@router.post("/reviews/report", response_model=ReviewReportResponse, tags=["AI Reporting"])
async def get_review_detail_report(payload: TriggerRequest):
    _, _, results = load_product_analysis(payload)
    return build_review_report(results)


@router.post("/products/risk-report", response_model=ProductRiskReportResponse, tags=["AI Reporting"])
async def get_product_risk_report(payload: TriggerRequest):
    product_id, reviews, results = load_product_analysis(payload)
    product_name = get_product_name(product_id) or f"알 수 없는 상품 ({product_id})"
    return build_risk_report(product_id, product_name, reviews, results)
