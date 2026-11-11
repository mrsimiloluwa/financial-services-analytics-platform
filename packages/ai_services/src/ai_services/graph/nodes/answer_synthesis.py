"""Node synthesizing governed business narrative from analytical query results."""

from __future__ import annotations

import json
import logging
from typing import Any

from ai_services.graph.state import AIAnalyticsState
from ai_services.providers.base import BaseLLMProvider
from ai_services.providers.factory import get_llm_provider
from ai_services.schemas import AnalyticsQueryResponse

logger = logging.getLogger(__name__)

ANSWER_SYNTHESIS_SYSTEM_PROMPT = """You are a senior commercial banking financial analyst.
Synthesize a professional, concise, and executive-ready financial narrative answering the user's question.

RULES:
1. Base all answers strictly on the provided SQL query results. Never hallucinate numbers.
2. State figures clearly with currency symbols (e.g., €121,675.00) and percentages (e.g., 94.72%).
3. When explaining revenue reconciliation or financial bridges, explicitly include all components: gross assessed fees, waivers, uncollected arrears, fee reversals (even when zero, e.g. €0.00), and pass-through costs.
4. Mention the governed metric used and any relevant reporting limitations.
5. Keep the summary focused, professional, and easy for finance leadership to review.
"""


def create_answer_synthesis_node(
    provider: BaseLLMProvider | None = None,
):
    """Create answer synthesis node generating business narrative and evidence payload."""
    llm = provider or get_llm_provider()

    def answer_synthesis_node(state: AIAnalyticsState) -> dict[str, Any]:
        question = state.get("question", "")
        understanding = state.get("understanding")
        metric = state.get("metric")
        validation = state.get("validation")
        result = state.get("query_result")
        generated_sql = state.get("generated_sql")

        # 1. Handle Out of Scope / Malicious
        if understanding and understanding.is_out_of_scope:
            reason = (
                understanding.rejection_reason
                or "Inquiry is outside the scope of commercial banking financial analytics."
            )
            response = AnalyticsQueryResponse(
                question=question,
                answer=reason,
                status="OUT_OF_SCOPE",
                confidence=1.0,
            )
            return {"final_response": response}

        # 2. Handle SQL Validation Security Rejection
        if validation and not validation.is_valid:
            error_msg = validation.error_message or "Query failed security validation."
            response = AnalyticsQueryResponse(
                question=question,
                answer=(
                    f"**Security Boundary Enforcement**: The requested inquiry could not be executed because "
                    f"the generated query violated security constraints: {error_msg}"
                ),
                status="REJECTED",
                sql_query=generated_sql,
                confidence=1.0,
                limitations="Enforced strictly by SQLGlot AST security validator and table allowlists.",
            )
            return {"final_response": response}

        # 3. Handle Database Execution Error
        if result and result.error:
            response = AnalyticsQueryResponse(
                question=question,
                answer=f"Database execution error encountered: {result.error}",
                status="ERROR",
                sql_query=generated_sql,
                execution_time_ms=result.execution_time_ms,
                confidence=0.0,
            )
            return {"final_response": response}

        # 4. Handle Successful Execution
        rows = result.rows if result else []
        columns = result.columns if result else []
        sample_rows_json = json.dumps(rows[:10], indent=2)

        prompt = (
            f"User Question: {question}\n\n"
            f"Governed Metric: {metric.metric_name if metric else 'Custom Metric'}\n"
            f"Metric Formula: {metric.formula if metric else 'N/A'}\n"
            f"Executed SQL:\n{generated_sql}\n\n"
            f"Query Results (Row Count: {len(rows)}):\n{sample_rows_json}\n\n"
            "Synthesize a clear, authoritative financial answer explaining these numbers."
        )

        try:
            narrative = llm.generate(
                prompt=prompt,
                system_prompt=ANSWER_SYNTHESIS_SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.warning("LLM answer synthesis failed, using formatted fallback: %s", exc)
            narrative = (
                f"Query executed successfully against {metric.source_model if metric else 'analytics warehouse'}. "
                f"Returned {len(rows)} records matching the inquiry criteria."
            )

        response = AnalyticsQueryResponse(
            question=question,
            answer=narrative,
            metric_used=metric.metric_name if metric else None,
            model_used=metric.source_model if metric else None,
            sql_query=generated_sql,
            data=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=result.execution_time_ms if result else 0.0,
            currency="EUR",
            reporting_period=understanding.time_period if understanding else None,
            confidence=metric.confidence if metric else 0.9,
            limitations=(
                "All monetary metrics are reported in EUR converted via synthetic daily mid-market FX rates. "
                "Analysis is restricted strictly to certified dimensional warehouse marts."
            ),
            status="SUCCESS",
        )

        return {"final_response": response}

    return answer_synthesis_node
