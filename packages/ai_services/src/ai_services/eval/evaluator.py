"""Evaluation framework executing curated benchmarks against AI analytics graph."""

from __future__ import annotations

import logging
import time

from ai_services.eval.dataset import EVALUATION_DATASET, EvaluationCase
from ai_services.graph.workflow import build_financial_analytics_graph
from ai_services.providers.base import BaseLLMProvider
from ai_services.providers.factory import get_llm_provider
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EvaluationCaseResult(BaseModel):
    """Result of evaluating a single test case."""

    case_id: str
    category: str
    passed: bool
    status: str
    actual_intent: str | None = None
    actual_metric_id: str | None = None
    actual_model: str | None = None
    sql_valid: bool | None = None
    error_message: str | None = None
    duration_ms: float = 0.0


class EvaluationSummary(BaseModel):
    """Aggregate statistics for an evaluation run."""

    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    accuracy_pct: float = 0.0
    security_defense_pct: float = 0.0
    category_scores: dict[str, float] = Field(default_factory=dict)
    duration_seconds: float = 0.0
    results: list[EvaluationCaseResult] = Field(default_factory=list)


class AIAnalyticsEvaluator:
    """Evaluates AI analytics workflow against certified financial questions and security attacks."""

    def __init__(
        self,
        provider: BaseLLMProvider | None = None,
        environment: str = "dev",
    ) -> None:
        """Initialize evaluator with provider and target environment."""
        self.provider = provider or get_llm_provider()
        self.environment = environment
        self.graph = build_financial_analytics_graph(provider=self.provider)

    def evaluate_case(self, case: EvaluationCase) -> EvaluationCaseResult:
        """Execute a single evaluation case and assert business correctness and security boundaries."""
        start_time = time.perf_counter()

        try:
            workflow_state = self.graph.invoke(
                {
                    "question": case.question,
                    "environment": self.environment,
                }
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            resp = workflow_state.get("final_response")
            understanding = workflow_state.get("understanding")
            metric = workflow_state.get("metric")
            validation = workflow_state.get("validation")

            if not resp:
                return EvaluationCaseResult(
                    case_id=case.case_id,
                    category=case.category,
                    passed=False,
                    status="NO_RESPONSE",
                    error_message="Workflow failed to produce a response.",
                    duration_ms=duration_ms,
                )

            passed = True
            error_reasons: list[str] = []

            # 1. Assert Out-of-Scope / Security Handling
            if case.is_out_of_scope:
                if resp.status not in ("OUT_OF_SCOPE", "REJECTED"):
                    passed = False
                    error_reasons.append(f"Expected OUT_OF_SCOPE/REJECTED, got {resp.status}")

                # Ensure forbidden SQL patterns were never generated or executed
                if resp.sql_query:
                    for pattern in case.forbidden_sql_patterns:
                        if pattern.lower() in resp.sql_query.lower():
                            passed = False
                            error_reasons.append(f"Forbidden pattern '{pattern}' found in SQL")

            # 2. Assert In-Scope Financial Questions
            else:
                if resp.status != "SUCCESS":
                    passed = False
                    error_reasons.append(
                        f"Expected SUCCESS status, got {resp.status}: {resp.answer}"
                    )

                # Check metric resolution if specified
                if (
                    case.expected_metric_id
                    and metric
                    and metric.metric_id != case.expected_metric_id
                    and not (case.expected_model and metric.source_model == case.expected_model)
                ):
                    passed = False
                    error_reasons.append(
                        f"Expected metric '{case.expected_metric_id}', got '{metric.metric_id}'"
                    )

                # Check SQL validation
                if validation and not validation.is_valid:
                    passed = False
                    error_reasons.append(f"SQL validation rejected: {validation.error_message}")

            return EvaluationCaseResult(
                case_id=case.case_id,
                category=case.category,
                passed=passed,
                status=resp.status,
                actual_intent=understanding.intent if understanding else None,
                actual_metric_id=metric.metric_id if metric else None,
                actual_model=metric.source_model if metric else None,
                sql_valid=validation.is_valid if validation else None,
                error_message="; ".join(error_reasons) if error_reasons else None,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return EvaluationCaseResult(
                case_id=case.case_id,
                category=case.category,
                passed=False,
                status="EXCEPTION",
                error_message=str(exc),
                duration_ms=duration_ms,
            )

    def run_suite(
        self,
        cases: list[EvaluationCase] | None = None,
    ) -> EvaluationSummary:
        """Execute full evaluation benchmark suite and calculate summary metrics."""
        suite = cases or EVALUATION_DATASET
        start_suite = time.perf_counter()

        results: list[EvaluationCaseResult] = []
        category_totals: dict[str, int] = {}
        category_passes: dict[str, int] = {}

        for case in suite:
            cat = case.category
            category_totals[cat] = category_totals.get(cat, 0) + 1

            result = self.evaluate_case(case)
            results.append(result)

            if result.passed:
                category_passes[cat] = category_passes.get(cat, 0) + 1

        total_cases = len(suite)
        passed_cases = sum(1 for r in results if r.passed)
        failed_cases = total_cases - passed_cases
        accuracy_pct = round((passed_cases / total_cases * 100), 2) if total_cases > 0 else 0.0

        sec_cases = [r for r in results if r.category == "security"]
        sec_passes = sum(1 for r in sec_cases if r.passed)
        security_defense_pct = round((sec_passes / len(sec_cases) * 100), 2) if sec_cases else 100.0

        category_scores = {
            cat: round((category_passes.get(cat, 0) / category_totals[cat] * 100), 2)
            for cat in category_totals
        }

        total_duration = round(time.perf_counter() - start_suite, 2)

        return EvaluationSummary(
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            accuracy_pct=accuracy_pct,
            security_defense_pct=security_defense_pct,
            category_scores=category_scores,
            duration_seconds=total_duration,
            results=results,
        )
