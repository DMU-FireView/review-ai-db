"""공통 analyze_reviews 진입점으로 분석하고 v0.5 결과를 저장한 뒤 반환한다."""
import logging

from app.contracts.data_ai_v05 import DataAnalyzeRequestV05, DataAnalyzeResponseV05
from app.repositories.analysis_jobs import JobStore
from app.services.analysis import analyze_reviews

LOGGER = logging.getLogger(__name__)


def evaluate_data_and_store(store: JobStore, job_id: str,
                            payload: DataAnalyzeRequestV05) -> DataAnalyzeResponseV05:
    try:
        # 운영 입력 계약은 그대로 유지한다. rating/written_at만으로 행동 근거를 만들지 않는다.
        # 실제로 제공되는 행동 evidence 확장은 Data 팀과 입력 계약을 합의한 뒤 연결한다.
        evaluated = analyze_reviews(
            platform=payload.platform, product_id=payload.product_id,
            reviews=[{"review_id": review.review_id, "content": review.content}
                     for review in payload.reviews],
        )
        response = DataAnalyzeResponseV05.model_validate(evaluated)
        store.complete(job_id, response.model_dump(mode="json"))
        return response
    except Exception:
        try:
            store.fail(job_id, "ANALYSIS_OR_STORAGE_FAILED")
        except Exception:
            LOGGER.exception("Failed to record Data analysis failure for %s", job_id)
        raise
