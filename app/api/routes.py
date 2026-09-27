"""운영 health API를 제공한다. 공식 분석은 data_analysis 라우터가 담당한다."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
