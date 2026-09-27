"""v0.4의 선택 review_count를 표현하는 검토용 응답 DTO를 제공한다."""
from typing import Self

from pydantic import Field, model_validator

from app.contracts.data_ai_result import ContractModel, DataAIResult, Identifier, ReviewResult


class DataAIResponse(ContractModel):
    """기존 결과 모델의 검증을 재사용하며 review_count 생략을 허용한다."""

    platform: Identifier
    product_id: Identifier
    results: list[ReviewResult]
    review_count: int | None = Field(default=None, strict=True, ge=0)

    @model_validator(mode="after")
    def validate_results(self) -> Self:
        # 결과 필드·중복·개수 검증은 기존 준비용 모델을 단일 기준으로 사용한다.
        DataAIResult.model_validate({
            "platform": self.platform,
            "product_id": self.product_id,
            "review_count": len(self.results) if self.review_count is None else self.review_count,
            "results": [result.model_dump() for result in self.results],
        })
        return self
