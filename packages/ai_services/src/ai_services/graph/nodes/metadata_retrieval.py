"""Node for retrieving schema and governance context for authorized dimensional models."""

from __future__ import annotations

import logging
from typing import Any

from ai_services.graph.state import AIAnalyticsState
from data_platform.metadata.extractor import QUERYABLE_ALLOWLIST
from data_platform.metadata.service import MetadataService

logger = logging.getLogger(__name__)


def create_metadata_retrieval_node(
    metadata_service: MetadataService | None = None,
):
    """Create metadata retrieval node pulling queryable model schemas and context."""
    meta = metadata_service or MetadataService()

    def metadata_retrieval_node(state: AIAnalyticsState) -> dict[str, Any]:
        understanding = state.get("understanding")
        if understanding and understanding.is_out_of_scope:
            return {"query_context": None}

        metric = state.get("metric")
        primary_model = (
            metric.source_model if metric and metric.source_model else "fct_customer_revenue"
        )

        # Ensure model is in allowlist
        if primary_model not in QUERYABLE_ALLOWLIST:
            logger.warning(
                "Target model '%s' not in allowlist, falling back to 'fct_customer_revenue'",
                primary_model,
            )
            primary_model = "fct_customer_revenue"

        logger.info("Retrieving query context for model: %s", primary_model)

        try:
            primary_ctx = meta.build_ai_query_context(primary_model)
            context_data: dict[str, Any] = primary_ctx.model_dump()

            # If the query asks for customer dimension details, attach dim_customers context
            dim_ctx = meta.build_ai_query_context("dim_customers")
            context_data["joinable_dimensions"] = [dim_ctx.model_dump()]

            return {"query_context": context_data}
        except Exception as exc:
            logger.error("Failed retrieving metadata context for '%s': %s", primary_model, exc)
            return {
                "query_context": {
                    "model_name": primary_model,
                    "schema": "analytics",
                    "columns": [],
                }
            }

    return metadata_retrieval_node
