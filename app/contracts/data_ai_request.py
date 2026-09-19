"""Data/AI v0.4 검토용 요청 DTO. 기존 API나 분석기 입력을 대체하지 않는다."""
from pydantic import Field

from app.contracts.data_ai_result import ContractModel, Identifier, ReviewIdentity


class DataAIReview(ContractModel):
    """본문과 원본 ID만 필수이며 누락된 선택값에 관측값을 만들어 넣지 않는다."""

    review_id: Identifier
    content: str = Field(strict=True, min_length=1)
    rating: float | None = Field(default=None, strict=True)
    written_at: str | None = Field(default=None, strict=True)


class DataAIRequest(ContractModel):
    """한 플랫폼·상품의 검토용 배치 요청. 상세 입력 정책은 합의 전이다."""

    platform: Identifier
    product_id: Identifier
    reviews: list[DataAIReview] = Field(min_length=1)

    def review_identities(self) -> list[ReviewIdentity]:
        """요청 순서와 원본 문자열을 유지해 순수 결과 매퍼에 전달한다."""
        return [
            ReviewIdentity(
                platform=self.platform,
                product_id=self.product_id,
                review_id=review.review_id,
            )
            for review in self.reviews
        ]
