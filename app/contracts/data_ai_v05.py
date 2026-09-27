"""Data/AI v0.5의 원본 식별자, 평면 점수, null과 사유 코드 계약을 정의한다."""
from typing import Self

from pydantic import Field, field_validator, model_validator

from app.contracts.data_ai_request import DataAIReview
from app.contracts.data_ai_result import ContractModel, Identifier, Level, Score
from app.scoring.meta_scorer import classify_rti


class DataReviewV05(DataAIReview):
    @field_validator("review_id", "content")
    @classmethod
    def reject_blank(cls, value):
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value  # 원본 값을 trim하지 않는다.


class DataAnalyzeRequestV05(ContractModel):
    platform: Identifier
    product_id: Identifier
    # O(n²) 비교 비용을 제한하는 우리 서버의 배치 상한. Data와 운영 한도 협의 필요.
    reviews: list[DataReviewV05] = Field(min_length=1, max_length=500)

    @field_validator("platform", "product_id")
    @classmethod
    def reject_blank(cls, value):
        if not value.strip():
            raise ValueError("Identifier must not be blank")
        return value

    @model_validator(mode="after")
    def unique_reviews(self) -> Self:
        ids = [review.review_id for review in self.reviews]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate review_id")
        return self


class DataReviewResultV05(ContractModel):
    review_id: Identifier
    rti: Score | None
    level: Level | None
    text_score: Score | None
    behavior_score: Score | None
    network_score: Score | None
    reasons: list[Identifier]

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.rti is None:
            if self.level is not None:
                raise ValueError("RTI null requires level=null")
        else:
            if all(value is None for value in (
                self.text_score, self.behavior_score, self.network_score
            )):
                raise ValueError("RTI requires at least one score")
            if self.level != classify_rti(self.rti).value:
                raise ValueError("Level must use safe>=80, warn>=50, danger<50")
        return self


class DataAnalyzeResponseV05(ContractModel):
    platform: Identifier
    product_id: Identifier
    review_count: int | None = Field(default=None, strict=True, ge=0)
    results: list[DataReviewResultV05]

    @model_validator(mode="after")
    def validate_results(self) -> Self:
        if self.review_count is not None and self.review_count != len(self.results):
            raise ValueError("review_count must equal results length")
        ids = [result.review_id for result in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate result review_id")
        return self
