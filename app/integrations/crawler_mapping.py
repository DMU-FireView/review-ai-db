"""크롤러 입력을 기존 평가 DTO에 연결하되 미합의 신호 추정은 차단한다."""
from app.api.schemas import ReviewInput
from app.contracts.crawler import CrawlerReview


class MappingNotApproved(ValueError):
    pass


def to_legacy_inputs(reviews: list[CrawlerReview], product_id: str,
                     *, allow_legacy_defaults: bool = False) -> list[ReviewInput]:
    # 원본에 없는 행동/유사도 필드를 새 알고리즘으로 계산하지 않는다.
    # 명시적으로 승인한 실험에서만 기존 DTO 기본값(일일 1건, 유사 0건)을 쓴다.
    if not allow_legacy_defaults:
        raise MappingNotApproved("Crawler scoring defaults require team approval")
    return [
        ReviewInput(
            review_id=f"{r.platform}:{r.review_id}",
            product_id=product_id,
            content=r.content,
            user_id=r.author or "",
            review_date=r.written_at.isoformat() if r.written_at else "",
            image_count=len(r.images),
        )
        for r in reviews
    ]
