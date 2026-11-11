"""Node for validating and sanitizing generated SQL using SQLGlot AST validator."""

from __future__ import annotations

import logging
from typing import Any

from ai_services.graph.state import AIAnalyticsState
from ai_services.schemas import SQLValidationResult
from ai_services.security.sql_validator import SQLGlotASTValidator

logger = logging.getLogger(__name__)


def create_sql_validation_node(
    validator: SQLGlotASTValidator | None = None,
):
    """Create SQL validation node enforcing AST security boundaries."""
    val = validator or SQLGlotASTValidator()

    def sql_validation_node(state: AIAnalyticsState) -> dict[str, Any]:
        understanding = state.get("understanding")
        if understanding and understanding.is_out_of_scope:
            return {"validation": None}

        generated_sql = state.get("generated_sql")
        if not generated_sql:
            validation = SQLValidationResult(
                is_valid=False,
                error_message="No SQL query was generated.",
            )
            return {"validation": validation}

        validation = val.validate_and_sanitize(generated_sql)
        updates: dict[str, Any] = {"validation": validation}

        if validation.is_valid and validation.sanitized_sql:
            updates["generated_sql"] = validation.sanitized_sql
            logger.info("SQL validation PASSED. Tables: %s", validation.tables_accessed)
        else:
            logger.warning("SQL validation REJECTED: %s", validation.error_message)

        return updates

    return sql_validation_node
