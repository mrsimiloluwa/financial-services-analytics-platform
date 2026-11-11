"""LangGraph compilation and orchestration workflow for AI Financial Analytics."""

from __future__ import annotations

import logging
from typing import Literal

from ai_services.execution.engine import SQLExecutionEngine
from ai_services.graph.nodes.answer_synthesis import create_answer_synthesis_node
from ai_services.graph.nodes.metadata_retrieval import create_metadata_retrieval_node
from ai_services.graph.nodes.metric_resolution import create_metric_resolution_node
from ai_services.graph.nodes.question_understanding import create_question_understanding_node
from ai_services.graph.nodes.result_validation import create_result_validation_node
from ai_services.graph.nodes.sql_execution import create_sql_execution_node
from ai_services.graph.nodes.sql_generation import create_sql_generation_node
from ai_services.graph.nodes.sql_validation import create_sql_validation_node
from ai_services.graph.state import AIAnalyticsState
from ai_services.providers.base import BaseLLMProvider
from ai_services.providers.factory import get_llm_provider
from ai_services.security.sql_validator import SQLGlotASTValidator
from data_platform.metadata.service import MetadataService
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)


def route_after_understanding(
    state: AIAnalyticsState,
) -> Literal["synthesize_answer", "resolve_metric"]:
    """Route early to synthesis if question is out-of-scope or a prompt injection."""
    understanding = state.get("understanding")
    if understanding and understanding.is_out_of_scope:
        return "synthesize_answer"
    return "resolve_metric"


def route_after_validation(
    state: AIAnalyticsState,
) -> Literal["synthesize_answer", "execute_sql"]:
    """Route directly to synthesis without executing if SQL validation failed."""
    validation = state.get("validation")
    if not validation or not validation.is_valid:
        return "synthesize_answer"
    return "execute_sql"


def build_financial_analytics_graph(
    provider: BaseLLMProvider | None = None,
    metadata_service: MetadataService | None = None,
    validator: SQLGlotASTValidator | None = None,
    execution_engine: SQLExecutionEngine | None = None,
):
    """Construct and compile the LangGraph state machine for governed financial Q&A."""
    llm = provider or get_llm_provider()
    meta = metadata_service or MetadataService()
    val = validator or SQLGlotASTValidator()

    # 1. Instantiate Graph
    workflow = StateGraph(AIAnalyticsState)

    # 2. Add Pipeline Nodes
    workflow.add_node("understand_question", create_question_understanding_node(llm))
    workflow.add_node("resolve_metric", create_metric_resolution_node(llm, meta))
    workflow.add_node("retrieve_metadata", create_metadata_retrieval_node(meta))
    workflow.add_node("generate_sql", create_sql_generation_node(llm))
    workflow.add_node("validate_sql", create_sql_validation_node(val))
    workflow.add_node("execute_sql", create_sql_execution_node(execution_engine))
    workflow.add_node("validate_results", create_result_validation_node())
    workflow.add_node("synthesize_answer", create_answer_synthesis_node(llm))

    # 3. Add Edges & Conditional Routing
    workflow.add_edge(START, "understand_question")

    workflow.add_conditional_edges(
        "understand_question",
        route_after_understanding,
        {
            "synthesize_answer": "synthesize_answer",
            "resolve_metric": "resolve_metric",
        },
    )

    workflow.add_edge("resolve_metric", "retrieve_metadata")
    workflow.add_edge("retrieve_metadata", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")

    workflow.add_conditional_edges(
        "validate_sql",
        route_after_validation,
        {
            "synthesize_answer": "synthesize_answer",
            "execute_sql": "execute_sql",
        },
    )

    workflow.add_edge("execute_sql", "validate_results")
    workflow.add_edge("validate_results", "synthesize_answer")
    workflow.add_edge("synthesize_answer", END)

    # 4. Compile State Machine
    return workflow.compile()
