"""Governed Financial Metric Catalog loader, parser, and schema validator."""

from __future__ import annotations

import logging
from pathlib import Path

import sqlglot
import yaml

from data_platform.metadata.schemas import DataClassification, FinancialMetric, ModelMetadata

logger = logging.getLogger(__name__)

DEFAULT_METRICS_PATH = Path(__file__).parent / "financial_metrics.yaml"


class MetricRegistry:
    """Manages governed enterprise financial metrics definitions."""

    def __init__(self, metrics: dict[str, FinancialMetric] | None = None) -> None:
        """Initialize registry with dictionary of metrics keyed by metric_id."""
        self._metrics: dict[str, FinancialMetric] = metrics or {}

    @classmethod
    def from_yaml(cls, yaml_path: Path | str = DEFAULT_METRICS_PATH) -> MetricRegistry:
        """Load governed metrics from a YAML definition file."""
        path = Path(yaml_path)
        if not path.is_file():
            raise FileNotFoundError(f"Financial metrics definition file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        metrics_data = data.get("metrics", [])
        metrics_dict: dict[str, FinancialMetric] = {}

        for item in metrics_data:
            classification = DataClassification(item.get("classification", "INTERNAL"))
            metric = FinancialMetric(
                metric_id=item["metric_id"],
                metric_name=item["metric_name"],
                business_definition=item["business_definition"],
                formula=item["formula"],
                source_model=item["source_model"],
                relevant_columns=item.get("relevant_columns", []),
                grain=item["grain"],
                aggregation_behavior=item["aggregation_behavior"],
                native_currency_treatment=item["native_currency_treatment"],
                reporting_currency_conversion=item["reporting_currency_conversion"],
                date_field=item["date_field"],
                applicable_filters=item.get("applicable_filters"),
                data_quality_requirements=item.get("data_quality_requirements"),
                classification=classification,
                example_business_questions=item.get("example_business_questions", []),
                known_limitations=item.get("known_limitations"),
            )
            metrics_dict[metric.metric_id] = metric

        return cls(metrics=metrics_dict)

    def get(self, metric_id: str) -> FinancialMetric | None:
        """Retrieve a governed metric by metric_id."""
        return self._metrics.get(metric_id)

    def list_all(self) -> list[FinancialMetric]:
        """Return all governed metrics in alphabetical order."""
        return [self._metrics[k] for k in sorted(self._metrics.keys())]

    def get_by_model(self, model_name: str) -> list[FinancialMetric]:
        """Return all metrics defined against a specific source model."""
        return [m for m in self._metrics.values() if m.source_model == model_name]


class MetricValidator:
    """Validates financial metric definitions against physical catalog models and columns."""

    def __init__(self, models: dict[str, ModelMetadata]) -> None:
        """Initialize validator with dictionary of parsed ModelMetadata."""
        self.models = models

    def validate_metric(self, metric: FinancialMetric) -> list[str]:
        """Validate an individual financial metric definition.

        Returns a list of validation failure error strings (empty if valid).
        """
        errors: list[str] = []

        # 1. Model Existence
        model = self.models.get(metric.source_model)
        if not model:
            # Check if model has a qualified prefix like model.dbt_analytics.
            matching = [
                m for name, m in self.models.items() if name.endswith(f".{metric.source_model}")
            ]
            if matching:
                model = matching[0]
            else:
                errors.append(
                    f"Metric '{metric.metric_id}': source model '{metric.source_model}' "
                    f"does not exist in catalog."
                )
                return errors

        # 2. Columns Existence
        for col in metric.relevant_columns:
            if col not in model.columns:
                errors.append(
                    f"Metric '{metric.metric_id}': column '{col}' does not exist in model "
                    f"'{model.name}'."
                )

        # 3. Formula SQL Syntax Validation
        try:
            sqlglot.parse_one(f"SELECT {metric.formula}", read="postgres")
        except Exception as exc:
            errors.append(
                f"Metric '{metric.metric_id}': formula '{metric.formula}' is not valid SQL: {exc}"
            )

        return errors

    def validate_all(self, registry: MetricRegistry) -> dict[str, list[str]]:
        """Validate all metrics in a registry, returning a mapping of metric_id -> errors."""
        results: dict[str, list[str]] = {}
        for metric in registry.list_all():
            errors = self.validate_metric(metric)
            if errors:
                results[metric.metric_id] = errors
        return results
