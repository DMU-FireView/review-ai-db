"""전달받은 리뷰를 기존 방식으로 분석하고 결과 저장 후 응답하는 HTTP API."""
from fastapi import APIRouter, Request, Response, HTTPException
from app.services.persisted_analysis import evaluate_and_store
from app.api.schemas import AnalyzeRequest, AnalyzeResponse, ReviewInput

router = APIRouter()


@router.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/v1/analyze", response_model=AnalyzeResponse, tags=["AI Analysis"])
def analyze(payload: AnalyzeRequest, request: Request, response: Response) -> AnalyzeResponse:
    # 동기 분석/선택적 Google 호출은 FastAPI의 thread pool에서 실행한다.
    reviews = [
        ReviewInput(
            product_id=payload.product_id,
            **review.model_dump(exclude={"account_age_days"}),
        )
        for review in payload.reviews
    ]
    store = request.app.state.job_store
    try:
        job_id = store.create(payload.model_dump(mode="json"))
        response.headers["X-Analysis-Job-ID"] = job_id
        return evaluate_and_store(store, job_id, payload.product_id, reviews)
    except Exception as exc:
        raise HTTPException(503, "Analysis or result storage failed") from exc
