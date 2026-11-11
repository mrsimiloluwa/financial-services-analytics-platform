"""Unit tests for dbt manifest parsing and indexing."""

from __future__ import annotations

import pytest
from data_platform.metadata.dbt_manifest import DbtManifestParser


@pytest.fixture
def sample_manifest_data() -> dict:
    """Mock dbt manifest.json containing sample models, sources, and tests."""
    return {
        "metadata": {
            "dbt_version": "1.8.0",
            "adapter_type": "postgres",
            "target_name": "dev",
            "generated_at": "2026-11-10T22:00:00Z",
        },
        "nodes": {
            "model.dbt_analytics.fct_transactions": {
                "resource_type": "model",
                "name": "fct_transactions",
                "database": "analytics_platform",
                "schema": "analytics",
                "relation_name": '"analytics_platform"."analytics"."fct_transactions"',
                "materialized": "table",
                "description": "Commercial transactions fact table.",
                "original_file_path": "models/marts/core/fct_transactions.sql",
                "tags": ["core", "finance"],
                "meta": {"grain": "transaction_id"},
                "columns": {
                    "transaction_id": {"description": "Primary key."},
                    "customer_id": {"description": "Customer foreign key."},
                },
                "depends_on": {"nodes": ["model.dbt_analytics.stg_transactions"]},
            },
            "test.dbt_analytics.unique_fct_transactions_transaction_id.123": {
                "resource_type": "test",
                "name": "unique",
                "column_name": "transaction_id",
                "depends_on": {"nodes": ["model.dbt_analytics.fct_transactions"]},
                "test_metadata": {"name": "unique"},
            },
        },
        "sources": {
            "source.dbt_analytics.raw.transactions": {
                "source_name": "raw",
                "name": "transactions",
                "database": "analytics_platform",
                "schema": "raw",
                "description": "Raw simulated banking transactions.",
                "columns": {
                    "transaction_id": {"data_type": "VARCHAR(64)", "description": "PK"},
                },
            }
        },
        "parent_map": {
            "model.dbt_analytics.fct_transactions": ["model.dbt_analytics.stg_transactions"],
        },
        "child_map": {
            "source.dbt_analytics.raw.transactions": ["model.dbt_analytics.stg_transactions"],
            "model.dbt_analytics.stg_transactions": ["model.dbt_analytics.fct_transactions"],
        },
    }


def test_manifest_parser_extracts_models(sample_manifest_data: dict) -> None:
    """Scenario 1: Manifest parser correctly extracts model metadata."""
    parser = DbtManifestParser(sample_manifest_data)
    models = parser.extract_models()

    assert "model.dbt_analytics.fct_transactions" in models
    model = models["model.dbt_analytics.fct_transactions"]
    assert model.name == "fct_transactions"
    assert model.layer == "marts"
    assert model.database == "analytics_platform"
    assert model.grain == "transaction_id"
    assert "transaction_id" in model.columns


def test_manifest_parser_extracts_sources(sample_manifest_data: dict) -> None:
    """Scenario 2: Manifest parser correctly extracts raw source metadata."""
    parser = DbtManifestParser(sample_manifest_data)
    sources = parser.extract_sources()

    assert "source.dbt_analytics.raw.transactions" in sources
    source = sources["source.dbt_analytics.raw.transactions"]
    assert source.source_name == "raw"
    assert source.table_name == "transactions"
    assert "model.dbt_analytics.stg_transactions" in source.downstream_models


def test_manifest_parser_links_tests(sample_manifest_data: dict) -> None:
    """Scenario 3: Manifest parser links test metadata to models and columns."""
    parser = DbtManifestParser(sample_manifest_data)
    models = parser.extract_models()

    model = models["model.dbt_analytics.fct_transactions"]
    col = model.columns["transaction_id"]
    assert "unique" in col.tests
    assert parser.total_tests == 1
