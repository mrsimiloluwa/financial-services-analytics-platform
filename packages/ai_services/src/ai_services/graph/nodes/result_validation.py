"""Node for validating query execution outputs and handling zero-row results."""

from __future__ import annotations

import logging
from typing import Any

from ai_services.graph.state import AIAnalyticsState

logger = logging.getLogger(__name__)


def create_result_validation_node():
    """Create result validation node verifying non-empty, error-free database outputs."""

    def result_validation_node(state: AIAnalyticsState) -> dict[str, Any]:
        result = state.get("query_result")
        if not result:
            return {}

        if result.error:
            logger.warning("Query execution reported error: %s", result.error)
            return {"error": result.error}

        if result.row_count == 0:
            logger.info("Query returned 0 rows for the specified constraints.")

        return {}

    return result_validation_node
