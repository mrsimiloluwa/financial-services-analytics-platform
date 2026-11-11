"""Unit tests for MetadataService queryable allowlist and AI query context generation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from data_platform.metadata.extractor import QUERYABLE_ALLOWLIST
from data_platform.metadata.schemas import ColumnMetadata, DataClassification, ModelMetadata
from data_platform.metadata.service import MetadataService


def test_allowlist_contains_marts_only() -> None:
    """Scenario 19: Allowlist includes finance and core marts, excluding staging and raw."""
    assert "fct_transactions" in QUERYABLE_ALLOWLIST
    assert "fct_fee_assessments" in QUERYABLE_ALLOWLIST
    assert "fct_customer_revenue" in QUERYABLE_ALLOWLIST
    assert "dim_customers" in QUERYABLE_ALLOWLIST
    assert "dim_accounts" in QUERYABLE_ALLOWLIST

    assert "stg_transactions" not in QUERYABLE_ALLOWLIST
    assert "stg_customers" not in QUERYABLE_ALLOWLIST
    assert "raw.transactions" not in QUERYABLE_ALLOWLIST
    assert "int_customer_revenue" not in QUERYABLE_ALLOWLIST


def test_service_blocks_non_queryable_model_for_ai() -> None:
    """Scenario 20: build_ai_query_context raises PermissionError for non-queryable models."""
    service = MetadataService(conn=MagicMock())

    with pytest.raises(PermissionError) as exc_info:
        service.build_ai_query_context("stg_transactions")

    assert "is not in the governed queryable allowlist" in str(exc_info.value)


def test_service_builds_ai_query_context_for_mart() -> None:
    """Test AI query context generation on authorized model."""
    mock_model = ModelMetadata(
        model_id="m1",
        name="fct_transactions",
        layer="marts",
        database="db",
        schema_name="analytics",
        relation_name="analytics.fct_transactions",
        materialization="table",
        description="Transactions fact table.",
        grain="transaction_id",
        classification=DataClassification.INTERNAL,
        columns={
            "transaction_id": ColumnMetadata(
                name="transaction_id", data_type="VARCHAR(64)", description="PK"
            ),
            "transaction_amount_eur": ColumnMetadata(
                name="transaction_amount_eur", data_type="NUMERIC", description="EUR Amount"
            ),
            "transaction_date": ColumnMetadata(
                name="transaction_date", data_type="DATE", description="Date"
            ),
            "secret_key": ColumnMetadata(
                name="secret_key", data_type="TEXT", classification=DataClassification.RESTRICTED
            ),
        },
    )

    service = MetadataService(conn=MagicMock())
    with (
        patch.object(service, "get_model", return_value=mock_model),
        patch.object(service, "list_metrics", return_value=[]),
    ):
        ctx = service.build_ai_query_context("fct_transactions")

        assert ctx.model_name == "fct_transactions"
        assert "transaction_id" in ctx.columns
        assert "transaction_amount_eur" in ctx.columns
        # Restricted columns must never be included in query context
        assert "secret_key" not in ctx.columns
        assert len(ctx.restrictions) >= 5
