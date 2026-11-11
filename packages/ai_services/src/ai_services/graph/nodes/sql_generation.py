"""Node for generating PostgreSQL analytical queries adhering to schema contracts."""

from __future__ import annotations

import logging
import re
from typing import Any

from ai_services.graph.state import AIAnalyticsState
from ai_services.providers.base import BaseLLMProvider
from ai_services.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

SQL_GENERATION_SYSTEM_PROMPT = """You are a senior PostgreSQL analytics engineer writing queries for commercial banking data.
Generate ONLY valid, read-only PostgreSQL 16 SELECT queries against certified dimensional models in the 'analytics' schema.

STRICT CONSTRAINTS:
1. ONLY SELECT statements. No INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or multiple statements.
2. Target ONLY models in the 'analytics' schema. Always use the schema prefix (e.g., analytics.fct_customer_revenue).
3. Follow governed metric formulas provided in the prompt. Do not invent metric logic.
4. Monetary calculations: Use the audited EUR conversion columns (*_eur) when comparing or aggregating across currencies.
5. If customer attributes (customer_name, customer_segment) are requested, JOIN analytics.dim_customers ON customer_id.
6. Always include a sensible ORDER BY and LIMIT clause (default LIMIT 1000).
7. Return ONLY the raw SQL statement without commentary or markdown quotes.
"""


def clean_sql_output(raw_output: str) -> str:
    """Extract clean SQL string from model response, stripping markdown fences."""
    cleaned = raw_output.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    return cleaned


def create_sql_generation_node(
    provider: BaseLLMProvider | None = None,
):
    """Create SQL generation node producing governed PostgreSQL queries."""
    llm = provider or get_llm_provider()

    def sql_generation_node(state: AIAnalyticsState) -> dict[str, Any]:
        understanding = state.get("understanding")
        if understanding and understanding.is_out_of_scope:
            return {"generated_sql": None}

        question = state.get("question", "")
        metric = state.get("metric")
        ctx = state.get("query_context") or {}

        primary_model = ctx.get("model_name", "fct_customer_revenue")
        columns = ctx.get("columns", [])
        column_summary = "\n".join(
            f"  - {c.get('name')}: {c.get('data_type')} ({c.get('description', '')})"
            for c in columns
            if isinstance(c, dict)
        )

        join_summary = ""
        joins = ctx.get("joinable_dimensions", [])
        if joins:
            for j in joins:
                j_cols = j.get("columns", [])
                join_summary += f"\nJoinable Dimension: analytics.{j.get('model_name')} on customer_id\nColumns:\n"
                join_summary += "\n".join(
                    f"  - {c.get('name')}: {c.get('data_type')}"
                    for c in j_cols
                    if isinstance(c, dict)
                )

        prompt = (
            f"User Question: {question}\n\n"
            f"Governed Metric: {metric.metric_name if metric else 'Custom Inquiry'}\n"
            f"Metric Formula: {metric.formula if metric else 'Direct aggregation'}\n"
            f"Primary Model: analytics.{primary_model}\n"
            f"Model Columns:\n{column_summary}\n"
            f"{join_summary}\n\n"
            "Generate the PostgreSQL 16 analytical query to answer the question accurately."
        )

        try:
            raw_sql = llm.generate(
                prompt=prompt,
                system_prompt=SQL_GENERATION_SYSTEM_PROMPT,
            )
            generated_sql = clean_sql_output(raw_sql)
            logger.info("Generated SQL:\n%s", generated_sql)
        except Exception as exc:
            logger.error("SQL generation failed: %s", exc)
            generated_sql = None

        return {"generated_sql": generated_sql}

    return sql_generation_node
