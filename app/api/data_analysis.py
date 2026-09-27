"""Data가 전달한 v0.5 리뷰 배치를 분석하고 DB 저장 후 평면 결과를 반환한다."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.data_ai_v05 import DataAnalyzeRequestV05, DataAnalyzeResponseV05
from app.core.internal_auth import require_internal_token
from app.services.data_analysis import evaluate_data_and_store

router = APIRouter(tags=["Data AI v0.5"], dependencies=[Depends(require_internal_token)])


@router.post("/api/v1/data/analyze", response_model=DataAnalyzeResponseV05)
def analyze_data(payload: DataAnalyzeRequestV05, request: Request,
                 response: Response) -> DataAnalyzeResponseV05:
    store = request.app.state.job_store
    try:
        job_id = store.create(payload.model_dump(mode="json"))
        result = evaluate_data_and_store(store, job_id, payload)
    except Exception as exc:
        raise HTTPException(503, "Analysis or result storage failed") from exc
    response.headers["X-Analysis-Job-ID"] = job_id
    return result
