"""기존 점수 계산을 호출하고 DB 커밋이 완료된 결과만 반환한다."""
import logging
from ai.analysis import analyze_review
from app.api.schemas import AnalyzeResponse, ReviewInput
from app.repositories.analysis_jobs import JobStore

LOGGER = logging.getLogger(__name__)


def evaluate_and_store(store: JobStore, job_id: str, product_id: str,
                       reviews: list[ReviewInput]) -> AnalyzeResponse:
    try:
        response = AnalyzeResponse(
            product_id=product_id,
            results=[analyze_review(review) for review in reviews],
        )
        store.complete(job_id, response.model_dump(mode="json"))
        return response
    except Exception:
        try:
            store.fail(job_id, "ANALYSIS_OR_STORAGE_FAILED")
        except Exception:
            LOGGER.exception("Failed to record analysis failure for %s", job_id)
        raise
