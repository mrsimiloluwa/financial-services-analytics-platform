"""Unit tests for governed financial metric catalog and validator."""

from __future__ import annotations

from pathlib import Path

import pytest
from data_platform.metadata.extractor import MetadataExtractor
from data_platform.metadata.metrics import MetricRegistry, MetricValidator
from data_platform.metadata.schemas import ColumnMetadata, FinancialMetric, ModelMetadata


def test_metric_registry_loads_12_metrics() -> None:
    """Scenario 15: Metric registry loads all 12 governed financial metrics."""
    registry = MetricRegistry.from_yaml()
    metrics = registry.list_all()

    assert len(metrics) == 12
    metric_ids = {m.metric_id for m in metrics}
    expected = {
        "gross_transaction_volume",
        "net_transaction_volume",
        "reversal_rate",
        "assessed_fees",
        "waived_fees",
        "collected_fees",
        "fee_collection_rate",
        "recognized_revenue",
        "net_customer_profitability",
        "average_customer_daily_balance",
        "billing_exception_rate",
        "effective_take_rate",
    }
    assert expected.issubset(metric_ids)


def test_metric_validator_valid_passes() -> None:
    """Scenario 16: Metric validator passes when model, columns, and SQL are valid."""
    models = {
        "fct_transactions": ModelMetadata(
            model_id="m1",
            name="fct_transactions",
            layer="marts",
            database="db",
            schema_name="sch",
            relation_name="rel",
            materialization="table",
            columns={
                "transaction_amount_eur": ColumnMetadata(
                    name="transaction_amount_eur", data_type="NUMERIC"
                ),
                "transaction_date": ColumnMetadata(name="transaction_date", data_type="DATE"),
            },
        )
    }

    metric = FinancialMetric(
        metric_id="test_vol",
        metric_name="Test Volume",
        business_definition="Def",
        formula="SUM(transaction_amount_eur)",
        source_model="fct_transactions",
        relevant_columns=["transaction_amount_eur"],
        grain="grain",
        aggregation_behavior="SUM",
        native_currency_treatment="EUR",
        reporting_currency_conversion="EUR",
        date_field="transaction_date",
    )

    validator = MetricValidator(models)
    errors = validator.validate_metric(metric)
    assert errors == []


def test_metric_validator_missing_model_fails() -> None:
    """Scenario 17: Metric validator fails if source model does not exist."""
    models: dict[str, ModelMetadata] = {}

    metric = FinancialMetric(
        metric_id="test_missing_model",
        metric_name="Missing Model Metric",
        business_definition="Def",
        formula="COUNT(*)",
        source_model="non_existent_model",
        relevant_columns=[],
        grain="grain",
        aggregation_behavior="COUNT",
        native_currency_treatment="None",
        reporting_currency_conversion="None",
        date_field="d",
    )

    validator = MetricValidator(models)
    errors = validator.validate_metric(metric)
    assert len(errors) == 1
    assert "does not exist in catalog" in errors[0]


def test_metric_validator_missing_column_fails() -> None:
    """Scenario 18: Metric validator fails if relevant column is missing in model."""
    models = {
        "fct_transactions": ModelMetadata(
            model_id="m1",
            name="fct_transactions",
            layer="marts",
            database="db",
            schema_name="sch",
            relation_name="rel",
            materialization="table",
            columns={
                "other_column": ColumnMetadata(name="other_column", data_type="TEXT"),
            },
        )
    }

    metric = FinancialMetric(
        metric_id="test_missing_col",
        metric_name="Missing Col Metric",
        business_definition="Def",
        formula="SUM(non_existent_col)",
        source_model="fct_transactions",
        relevant_columns=["non_existent_col"],
        grain="grain",
        aggregation_behavior="SUM",
        native_currency_treatment="None",
        reporting_currency_conversion="None",
        date_field="d",
    )

    validator = MetricValidator(models)
    errors = validator.validate_metric(metric)
    assert len(errors) >= 1
    assert any("does not exist in model" in e for e in errors)


def test_all_12_governed_metrics_validate_against_actual_models() -> None:
    """Verify that all 12 metrics in financial_metrics.yaml pass validation against real dbt manifest."""
    target_dir = Path("packages/data_platform/dbt_analytics/target")
    if not (target_dir / "manifest.json").exists():
        pytest.skip("dbt target artifacts not found")

    extractor = MetadataExtractor(target_dir=target_dir)
    snapshot = extractor.extract()

    # Verify 0 validation errors across all 12 metrics
    assert snapshot.validation_errors == {}
    assert len(snapshot.metrics) == 12
