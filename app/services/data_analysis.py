"""정규화 리뷰를 승인된 팀원 분석기로 평가하고 v0.5 결과를 DB에 저장한다."""
import logging

from app.contracts.data_ai_v05 import DataAnalyzeRequestV05, DataAnalyzeResponseV05
from app.integrations.data_ai_v05_mapping import map_v05_results
from app.repositories.analysis_jobs import JobStore
from app.services.team_analysis import ReviewAnalysisInput, analyze_product_reviews

LOGGER = logging.getLogger(__name__)


def evaluate_data_and_store(store: JobStore, job_id: str,
                            payload: DataAnalyzeRequestV05) -> DataAnalyzeResponseV05:
    try:
        inputs = tuple(ReviewAnalysisInput(
            review_id=review.review_id, product_id=payload.product_id, content=review.content,
        ) for review in payload.reviews)
        # rating은 모델 입력이 아니다. written_at만으로 행동 근거를 만들지 않는다.
        # Google adapter / 학습 모델은 자동 활성화하지 않는다. 팀원 API와 같은 baseline.
        evaluated = analyze_product_reviews(payload.product_id, inputs)
        response = map_v05_results(payload, evaluated)
        store.complete(job_id, response.model_dump(mode="json"))
        return response
    except Exception:
        try:
            store.fail(job_id, "ANALYSIS_OR_STORAGE_FAILED")
        except Exception:
            LOGGER.exception("Failed to record Data analysis failure for %s", job_id)
        raise
