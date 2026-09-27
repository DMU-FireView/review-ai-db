"""ASGI entry point kept stable for the backend and deployment scripts."""

from app.factory import create_app
from ai.analysis import analyze_review as analyze_single_review
from app.api.schemas import (
    AnalysisResult,
    IncomingReview,
    InputFeatures,
    ReasonObject,
    ReviewInput,
    SignalScores,
)
from app.services.analysis import prepare_review_input


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
