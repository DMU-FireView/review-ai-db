"""백엔드와 합의한 내부 API 경로 및 응답 모델을 검증한다."""

import ast
from pathlib import Path

EXPECTED_RESPONSES = {
    "/api/internal/ai/products/product-list": "SummaryResponse",
    "/api/internal/ai/reviews/product-detail": "BatchResponse",
    "/api/internal/ai/products/rti-trend": "TrendResponse",
    "/api/internal/ai/reviews/report": "ReviewReportResponse",
    "/api/internal/ai/products/risk-report": "ProductRiskReportResponse",
}

EXPECTED_FIELDS = {
    "TriggerRequest": ["product_id", "url", "page_url", "product_url"],
    "ReviewInput": [
        "review_id",
        "product_id",
        "user_id",
        "content",
        "review_date",
        "rating",
        "image_count",
        "quality_score",
        "verified_purchase",
        "repurchase",
        "free_trial",
        "reviews_written_today",
        "similar_review_count",
    ],
    "SignalScores": ["text", "behavior", "network"],
    "ReasonObject": ["code", "message"],
    "InputFeatures": [
        "image_count",
        "quality_score",
        "verified_purchase",
        "repurchase",
        "free_trial",
        "reviews_written_today",
        "similar_review_count",
    ],
    "ProductSummaryResult": [
        "product_id",
        "average_rti",
        "level",
        "review_count",
        "safe_count",
        "warn_count",
        "danger_count",
    ],
    "SummaryResponse": ["products"],
    "AnalysisResult": [
        "review_id",
        "content",
        "author",
        "date",
        "rti",
        "level",
        "signals",
        "input_features",
        "reasons",
    ],
    "BatchResponse": ["results"],
    "TrendItem": [
        "date",
        "average_rti",
        "review_count",
        "safe_count",
        "warn_count",
        "danger_count",
    ],
    "TrendResponse": ["trend"],
    "ReasonDetail": ["title", "description"],
    "ReviewReportResponse": ["review_id", "rti", "signals", "reasons"],
    "SummaryStat": [
        "total_reviews",
        "average_rti",
        "danger_count",
        "warn_count",
        "safe_count",
    ],
    "SampleReview": [
        "review_id",
        "author",
        "date",
        "rating",
        "content",
        "level",
        "reasons",
    ],
    "ProductRiskReportResponse": [
        "product_id",
        "product_name",
        "summary_stat",
        "trend",
        "sample_reviews",
    ],
}


def main() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "app" / "api" / "routes.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    actual_responses: dict[str, str] = {}
    prefix = "/api/internal/ai"

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            func = decorator.func
            if (
                not isinstance(func, ast.Attribute)
                or func.attr != "post"
                or not isinstance(decorator.args[0], ast.Constant)
            ):
                continue
            response_model = next(
                (
                    keyword.value.id
                    for keyword in decorator.keywords
                    if keyword.arg == "response_model"
                    and isinstance(keyword.value, ast.Name)
                ),
                None,
            )
            path = prefix + decorator.args[0].value
            actual_responses[path] = response_model

    assert actual_responses == EXPECTED_RESPONSES, (
        f"API contract changed:\nexpected={EXPECTED_RESPONSES}\n"
        f"actual={actual_responses}"
    )

    schema_source = source.with_name("schemas.py")
    schema_tree = ast.parse(schema_source.read_text(encoding="utf-8"))
    actual_fields = {
        node.name: [
            item.target.id
            for item in node.body
            if isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
        ]
        for node in schema_tree.body
        if isinstance(node, ast.ClassDef) and node.name in EXPECTED_FIELDS
    }
    assert actual_fields == EXPECTED_FIELDS, (
        f"DTO contract changed:\nexpected={EXPECTED_FIELDS}\n"
        f"actual={actual_fields}"
    )

    print(
        "API contract OK: "
        f"{len(EXPECTED_RESPONSES)} endpoints, "
        f"{len(EXPECTED_FIELDS)} DTOs"
    )


if __name__ == "__main__":
    main()
