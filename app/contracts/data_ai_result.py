"""Data/AI v0.4 검토본의 식별자와 결과 형식을 정의한다. 운영 API에는 미연결이다."""
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(strict=True, min_length=1)]
Score = Annotated[float, Field(strict=True, ge=0, le=100)]
SignalName = Literal["text", "behavior", "network"]
Level = Literal["safe", "warn", "danger"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ReviewIdentity(ContractModel):
    """Data 원본 식별자. 숫자 변환·trim·접두사 추가 없이 그대로 보존한다."""

    platform: Identifier
    product_id: Identifier
    review_id: Identifier


class SignalResult(ContractModel):
    """분석기가 명시한 가용성과 점수만 받으며 누락 근거를 추정하지 않는다."""

    available: bool = Field(strict=True)
    score: Score | None
    unavailable_reasons: list[Identifier]

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.available:
            if self.score is None or self.unavailable_reasons:
                raise ValueError("Available signal requires a score and no unavailable reasons")
        elif self.score is not None:
            raise ValueError("Unavailable signal must have score=null")
        return self


class Signals(ContractModel):
    text: SignalResult
    behavior: SignalResult
    network: SignalResult


class AnalysisReason(ContractModel):
    source: SignalName
    code: Identifier
    message: str = Field(strict=True)


class ReviewEvaluation(ContractModel):
    """계산 완료 결과 경계. RTI/등급/가용성/사유 출처는 호출자가 결정한다."""

    rti_available: bool = Field(strict=True)
    rti: Score | None
    level: Level | None
    signals: Signals
    reasons: list[AnalysisReason]

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.rti_available:
            if self.rti is None or self.level is None:
                raise ValueError("Available RTI requires a score and level")
            if not any(signal.available for signal in (
                self.signals.text, self.signals.behavior, self.signals.network
            )):
                raise ValueError("Available RTI requires at least one available signal")
        elif self.rti is not None or self.level is not None:
            raise ValueError("Unavailable RTI must have rti=null and level=null")
        return self


class IdentifiedEvaluation(ContractModel):
    """분석 결과를 원본의 세 식별자에 명시적으로 연결한다."""

    identity: ReviewIdentity
    evaluation: ReviewEvaluation


class ReviewResult(ReviewEvaluation):
    review_id: Identifier


class DataAIResult(ContractModel):
    platform: Identifier
    product_id: Identifier
    review_count: int = Field(strict=True, ge=0)
    results: list[ReviewResult]

    @model_validator(mode="after")
    def validate_results(self) -> Self:
        if self.review_count != len(self.results):
            raise ValueError("review_count must equal results length")
        ids = [result.review_id for result in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate result review_id")
        return self
