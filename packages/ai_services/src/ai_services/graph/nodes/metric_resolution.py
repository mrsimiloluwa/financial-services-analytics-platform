"""Node for mapping questions to governed financial metrics using metadata catalog."""

from __future__ import annotations

import logging
from typing import Any

from ai_services.graph.state import AIAnalyticsState
from ai_services.providers.base import BaseLLMProvider
from ai_services.providers.factory import get_llm_provider
from ai_services.schemas import MetricResolution
from data_platform.metadata.service import MetadataService

logger = logging.getLogger(__name__)

METRIC_RESOLUTION_SYSTEM_PROMPT = """You are a financial governance assistant mapping user inquiries to certified financial metrics.
Select the single best matching metric from the governed financial metric catalog.
Do not invent new metrics or change existing formulas. If an exact metric is not defined, choose the closest dimensional mart model.
"""


def create_metric_resolution_node(
    provider: BaseLLMProvider | None = None,
    metadata_service: MetadataService | None = None,
):
    """Create a metric resolution node using governed catalog metadata."""
    llm = provider or get_llm_provider()
    meta = metadata_service or MetadataService()

    def metric_resolution_node(state: AIAnalyticsState) -> dict[str, Any]:
        understanding = state.get("understanding")
        if understanding and understanding.is_out_of_scope:
            logger.info("Skipping metric resolution for out-of-scope inquiry.")
            return {"metric": None}

        question = state.get("question", "")

        try:
            available_metrics = meta.list_metrics()
        except Exception as exc:
            logger.warning("Could not fetch metrics from MetadataService: %s", exc)
            available_metrics = []

        # Build catalog summary for LLM context
        catalog_summary = "\n".join(
            f"- {m.metric_id}: '{m.metric_name}' (Model: {m.source_model}) - Formula: {m.formula}. Definition: {m.business_definition}"
            for m in available_metrics
        )

        prompt = (
            f"User Question: {question}\n\n"
            f"Available Governed Metrics:\n{catalog_summary}\n\n"
            "Identify the target governed metric, its source model, and formula."
        )

        try:
            resolved = llm.generate_structured(
                prompt=prompt,
                response_model=MetricResolution,
                system_prompt=METRIC_RESOLUTION_SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.warning("Failed structured generation for metric resolution: %s", exc)
            resolved = MetricResolution(
                metric_id="recognized_revenue",
                metric_name="Recognized Revenue",
                source_model="fct_customer_revenue",
                formula="SUM(net_recognized_revenue_eur)",
                confidence=0.8,
            )

        # Enforce governed catalog as authoritative source of truth for formula and source model
        if resolved.metric_id and available_metrics:
            matched = next(
                (m for m in available_metrics if m.metric_id == resolved.metric_id), None
            )
            if matched:
                resolved.metric_name = matched.metric_name
                resolved.source_model = matched.source_model
                resolved.formula = matched.formula

        # Default source model if still unassigned
        if not resolved.source_model:
            resolved.source_model = "fct_customer_revenue"

        logger.info(
            "Resolved metric '%s' on model '%s' (Confidence: %.2f)",
            resolved.metric_id,
            resolved.source_model,
            resolved.confidence,
        )

        return {"metric": resolved}

    return metric_resolution_node
