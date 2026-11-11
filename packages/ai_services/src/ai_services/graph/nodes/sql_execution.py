"""Node for executing validated queries under least-privilege analytics_reader role."""

from __future__ import annotations

import logging
from typing import Any

from ai_services.execution.engine import SQLExecutionEngine
from ai_services.graph.state import AIAnalyticsState

logger = logging.getLogger(__name__)


def create_sql_execution_node(
    engine: SQLExecutionEngine | None = None,
):
    """Create SQL execution node using least-privilege role."""

    def sql_execution_node(state: AIAnalyticsState) -> dict[str, Any]:
        validation = state.get("validation")
        if not validation or not validation.is_valid:
            logger.info("Skipping execution: SQL validation failed or missing.")
            return {"query_result": None}

        sql_to_run = validation.sanitized_sql or state.get("generated_sql")
        if not sql_to_run:
            return {"query_result": None}

        env = state.get("environment", "dev")
        use_test_db = env.lower() == "test"

        exec_engine = engine or SQLExecutionEngine(use_test_db=use_test_db)
        logger.info("Executing analytical query on %s environment...", env.upper())

        query_result = exec_engine.execute_query(sql_to_run)
        return {"query_result": query_result}

    return sql_execution_node
