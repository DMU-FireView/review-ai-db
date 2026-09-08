"""Data 서버가 전달한 리뷰만 분석하는 HTTP API."""
from fastapi import APIRouter
from ai.analysis import analyze_review
from app.api.schemas import AnalyzeRequest, AnalyzeResponse, ReviewInput

router = APIRouter()


@router.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/v1/analyze", response_model=AnalyzeResponse, tags=["AI Analysis"])
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    # 동기 분석/선택적 Google 호출은 FastAPI의 thread pool에서 실행한다.
    reviews = [
        ReviewInput(
            product_id=payload.product_id,
            **review.model_dump(exclude={"account_age_days"}),
        )
        for review in payload.reviews
    ]
    return AnalyzeResponse(
        product_id=payload.product_id,
        results=[analyze_review(review) for review in reviews],
    )
