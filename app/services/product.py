"""상품별 RTI 요약·추이·리뷰 보고서 응답을 조립한다."""

from collections import defaultdict
from datetime import datetime, timedelta

from app.api.schemas import (
    AnalysisResult,
    ProductRiskReportResponse,
    ProductSummaryResult,
    ReasonDetail,
    ReviewInput,
    ReviewReportResponse,
    SampleReview,
    SummaryStat,
    TrendItem,
)


def build_trend(
    results: list[AnalysisResult], reviews: list[ReviewInput]
) -> list[TrendItem]:
    grouped = defaultdict(
        lambda: {
            "rti_sum": 0,
            "count": 0,
            "safe": 0,
            "warn": 0,
            "danger": 0,
        }
    )
    for result, review in zip(results, reviews):
        date = review.review_date[:10]
        grouped[date]["count"] += 1
        grouped[date]["rti_sum"] += result.rti
        grouped[date][result.level] += 1

    trend = []
    today = datetime.now().date()
    for offset in range(29, -1, -1):
        date = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        data = grouped.get(
            date,
            {
                "rti_sum": 0,
                "count": 0,
                "safe": 0,
                "warn": 0,
                "danger": 0,
            },
        )
        average = (
            round(data["rti_sum"] / data["count"], 2)
            if data["count"]
            else 0.0
        )
        trend.append(
            TrendItem(
                date=date,
                average_rti=average,
                review_count=data["count"],
                safe_count=data["safe"],
                warn_count=data["warn"],
                danger_count=data["danger"],
            )
        )
    return trend


def build_summary(
    product_id: str, results: list[AnalysisResult]
) -> ProductSummaryResult | None:
    if not results:
        return None
    safe = sum(result.level == "safe" for result in results)
    warn = sum(result.level == "warn" for result in results)
    danger = sum(result.level == "danger" for result in results)
    return ProductSummaryResult(
        product_id=product_id,
        average_rti=round(sum(result.rti for result in results) / len(results), 2),
        level="danger" if danger else "warn" if warn else "safe",
        review_count=len(results),
        safe_count=safe,
        warn_count=warn,
        danger_count=danger,
    )


def build_review_report(results: list[AnalysisResult]) -> ReviewReportResponse:
    if not results:
        return ReviewReportResponse(
            review_id="unknown",
            rti=100,
            signals={"text": 100, "behavior": 100, "network": 100},
            reasons=[],
        )
    target = next(
        (result for result in results if result.level == "danger"), results[0]
    )
    return ReviewReportResponse(
        review_id=target.review_id,
        rti=target.rti,
        signals=target.signals,
        reasons=[
            ReasonDetail(
                title=reason.message,
                description=f"[{reason.code}] 분석 엔진 감지 결과",
            )
            for reason in target.reasons
        ],
    )


def build_risk_report(
    product_id: str,
    product_name: str,
    reviews: list[ReviewInput],
    results: list[AnalysisResult],
) -> ProductRiskReportResponse:
    if not results:
        return ProductRiskReportResponse(
            product_id=product_id,
            product_name="데이터 없음",
            summary_stat=SummaryStat(
                total_reviews=0,
                average_rti=0.0,
                danger_count=0,
                warn_count=0,
                safe_count=0,
            ),
            trend=[],
            sample_reviews=[],
        )

    safe = sum(result.level == "safe" for result in results)
    warn = sum(result.level == "warn" for result in results)
    danger = sum(result.level == "danger" for result in results)
    samples = [
        SampleReview(
            review_id=result.review_id,
            author=review.user_id,
            date=review.review_date.replace("-", "."),
            rating=review.rating,
            content=review.content,
            level=result.level,
            reasons=result.reasons,
        )
        for result, review in zip(results, reviews)
        if result.level in {"danger", "warn"}
    ]
    return ProductRiskReportResponse(
        product_id=product_id,
        product_name=product_name,
        summary_stat=SummaryStat(
            total_reviews=len(results),
            average_rti=round(
                sum(result.rti for result in results) / len(results), 2
            ),
            danger_count=danger,
            warn_count=warn,
            safe_count=safe,
        ),
        trend=build_trend(results, reviews),
        sample_reviews=samples,
    )
