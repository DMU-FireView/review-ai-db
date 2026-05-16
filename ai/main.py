from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Any

# 기존 분석 모듈 로드
from text_analyzer import calculate_text_score
from behavior_analyzer import calculate_behavior_score
from network_analyzer import calculate_network_score

app = FastAPI(title="Re:view AI Analysis Server", version="v0.1")

# --- Pydantic 스키마 정의 (명세서 기준) ---
class ReviewInput(BaseModel):
    review_id: Any
    product_id: Any
    user_id: str
    rating: int
    content: str
    review_date: Optional[str] = None
    image_count: int = 0
    quality_score: Optional[float] = None
    verified_purchase: Optional[Any] = "unknown"
    repurchase: Optional[Any] = "unknown"
    free_trial: Optional[Any] = "unknown"
    reviews_written_today: Optional[int] = 1
    similar_review_count: int = 0

class BatchRequest(BaseModel):
    reviews: List[ReviewInput]

class ReasonObject(BaseModel):
    code: str
    message: str

class SignalScores(BaseModel):
    text: int
    behavior: int
    network: int

class AnalysisResult(BaseModel):
    review_id: Any
    product_id: Any
    rti: int
    level: str
    signals: SignalScores
    reasons: List[ReasonObject]

class BatchResponse(BaseModel):
    results: List[AnalysisResult]


# --- 등급 산정 헬퍼 함수 ---
def get_level(rti: int, reasons: list) -> str:
    if rti < 50:
        return "danger"
    if rti < 80:
        return "warn"
    
    # 재구매 신호 외에 페널티 사유가 하나라도 있으면 warn 처리
    penalty_reasons = [r for r in reasons if r["code"] != "REPURCHASE_SIGNAL"]
    if len(penalty_reasons) > 0:
        return "warn"
    
    return "safe"


# --- API Endpoint ---
@app.post("/api/ai/reviews/analyze-batch", response_model=BatchResponse)
async def analyze_reviews_batch(payload: BatchRequest):
    analysis_results = []

    for review in payload.reviews:
        # 1. 각 모듈별 점수 및 사유 계산
        text_score, text_reasons = calculate_text_score(review.content, review.quality_score)
        
        # behavior/network는 dict 형태를 받으므로 모델을 dict로 변환하여 전달
        review_dict = review.model_dump()
        behavior_score, behavior_reasons = calculate_behavior_score(review_dict)
        network_score, network_reasons = calculate_network_score(review_dict)

        # 2. RTI 최종 점수 결합 (v0 가중치: Text 40%, Behavior 35%, Network 25%)
        rti_score = round(
            text_score * 0.4
            + behavior_score * 0.35
            + network_score * 0.25
        )

        # 3. 사유(reasons) 통합 및 등급 결정
        all_reasons = text_reasons + behavior_reasons + network_reasons
        level = get_level(rti_score, all_reasons)

        # 4. 결과 포맷팅
        analysis_results.append(
            AnalysisResult(
                review_id=review.review_id,
                product_id=review.product_id,
                rti=rti_score,
                level=level,
                signals=SignalScores(
                    text=text_score,
                    behavior=behavior_score,
                    network=network_network_score if 'network_network_score' in locals() else network_score
                ),
                reasons=[ReasonObject(**r) for r in all_reasons]
            )
        )

    return BatchResponse(results=analysis_results)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)