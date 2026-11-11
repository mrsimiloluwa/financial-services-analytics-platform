"""LangGraph state schema for financial analytics question-answering workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from ai_services.schemas import (
    AnalyticsQueryResponse,
    MetricResolution,
    QueryResult,
    QuestionUnderstanding,
    SQLValidationResult,
)


class AIAnalyticsState(TypedDict, total=False):
    """Execution state propagated across LangGraph workflow nodes."""

    question: str
    environment: str
    conversation_id: str | None
    understanding: QuestionUnderstanding | None
    metric: MetricResolution | None
    query_context: dict[str, Any] | None
    generated_sql: str | None
    validation: SQLValidationResult | None
    query_result: QueryResult | None
    final_response: AnalyticsQueryResponse | None
    error: str | None
