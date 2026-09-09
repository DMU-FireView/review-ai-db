"""기본 비활성화된 임시 수집/SSE·결과 재조회 API를 제공한다."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from app.contracts.crawler import CollectStreamRequest
from app.services.collection_stream import collection_events

router = APIRouter(prefix="/experimental", tags=["Experimental - contract pending"])


@router.post("/analysis/collect/stream")
async def collect(payload: CollectStreamRequest, request: Request):
    if not request.app.state.allow_legacy_defaults:
        raise HTTPException(503, "Crawler scoring mapping is not approved")
    store = request.app.state.job_store
    try:
        job_id = await run_in_threadpool(store.create, payload.model_dump(mode="json"))
    except Exception as exc:
        raise HTTPException(503, "Job storage unavailable") from exc
    return StreamingResponse(
        collection_events(request.app.state.crawler_stream, store, job_id, payload,
                          allow_legacy_defaults=True),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no",
                 "X-Analysis-Job-ID": job_id},
    )


@router.get("/analysis/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    row = request.app.state.job_store.get(job_id)
    if row is None:
        raise HTTPException(404, "Job not found")
    # 원본 리뷰/요청은 공개하지 않는다. 인증 확정 전 전체 router 비활성화.
    return {key: row[key] for key in ("job_id", "status", "result", "error_code")}
