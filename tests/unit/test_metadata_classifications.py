"""Unit tests for data classification engine."""

from __future__ import annotations

from data_platform.metadata.classifications import ClassificationEngine
from data_platform.metadata.schemas import (
    ColumnMetadata,
    DataClassification,
    ModelMetadata,
    SourceMetadata,
)


def test_classification_default_sensitivity() -> None:
    """Scenario 5: Default sensitivity is INTERNAL for models and CONFIDENTIAL for sources."""
    engine = ClassificationEngine()

    model = ModelMetadata(
        model_id="m1",
        name="test_model",
        layer="staging",
        database="db",
        schema_name="sch",
        relation_name="rel",
        materialization="view",
    )
    engine.classify_model(model)
    assert model.classification == DataClassification.INTERNAL

    source = SourceMetadata(
        source_id="s1",
        source_name="raw",
        table_name="test_table",
        database="db",
        schema_name="raw",
    )
    engine.classify_source(source)
    assert source.classification == DataClassification.CONFIDENTIAL


def test_classification_pattern_detection() -> None:
    """Scenario 6: Column name heuristics identify CONFIDENTIAL and RESTRICTED tiers."""
    engine = ClassificationEngine()

    conf_col = ColumnMetadata(name="customer_id", data_type="VARCHAR")
    engine.classify_column(conf_col)
    assert conf_col.classification == DataClassification.CONFIDENTIAL

    restr_col = ColumnMetadata(name="api_secret_token", data_type="VARCHAR")
    engine.classify_column(restr_col)
    assert restr_col.classification == DataClassification.RESTRICTED

    normal_col = ColumnMetadata(name="status", data_type="VARCHAR")
    engine.classify_column(normal_col, parent_classification=DataClassification.INTERNAL)
    assert normal_col.classification == DataClassification.INTERNAL


def test_classification_meta_override() -> None:
    """Scenario 7: Explicit meta classification overrides defaults."""
    engine = ClassificationEngine()

    model = ModelMetadata(
        model_id="m2",
        name="public_summary",
        layer="marts",
        database="db",
        schema_name="sch",
        relation_name="rel",
        materialization="table",
    )
    raw_node = {"meta": {"classification": "PUBLIC"}}
    engine.classify_model(model, raw_node=raw_node)
    assert model.classification == DataClassification.PUBLIC


def test_classification_secret_redaction() -> None:
    """Scenario 8: Secret redaction masks restricted fields from outputs."""
    raw_data = {
        "model_name": "fct_transactions",
        "api_key": "sensitive_token_123",
        "safe_value": "normal_data",
    }
    cleaned = ClassificationEngine.redact_confidential_metadata(raw_data)
    assert cleaned["api_key"] == "[REDACTED_SECRET]"
    assert cleaned["model_name"] == "fct_transactions"
    assert cleaned["safe_value"] == "normal_data"
