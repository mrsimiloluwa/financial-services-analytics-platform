"""Integration tests for PostgreSQL metadata catalog repository against analytics_platform_test."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from data_platform.metadata.extractor import MetadataExtractor, MetadataSnapshot
from data_platform.metadata.repository import MetadataRepository
from data_platform.metadata.schemas import ArtifactRun
from shared.db import get_test_postgres_connection


def test_metadata_repository_persistence_and_queries() -> None:
    """Verify transactional persistence and query methods of MetadataRepository."""
    target_dir = Path("packages/data_platform/dbt_analytics/target")
    if not (target_dir / "manifest.json").exists():
        pytest.skip("dbt compilation target artifacts not found.")

    extractor = MetadataExtractor(target_dir=target_dir, environment="test")
    snapshot = extractor.extract()

    with get_test_postgres_connection() as conn:
        repo = MetadataRepository(conn)

        # 1. Save Snapshot
        repo.save_snapshot(snapshot)

        # 2. Query Latest Artifact Run
        latest_run = repo.get_latest_artifact_run(environment="test")
        assert latest_run is not None
        assert latest_run.environment == "test"
        assert latest_run.total_models == 26
        assert latest_run.total_sources == 12
        assert latest_run.total_tests == 462

        # 3. Query Allowlisted Marts
        marts = repo.list_queryable_models()
        assert len(marts) == 9
        mart_names = {m.name for m in marts}
        assert "fct_transactions" in mart_names
        assert "dim_customers" in mart_names

        # 4. Check specific model columns
        fct_txn = repo.get_model("fct_transactions")
        assert fct_txn is not None
        assert "transaction_id" in fct_txn.columns
        assert "transaction_amount_eur" in fct_txn.columns

        # 5. Check Governed Metrics
        metrics = repo.list_metrics()
        assert len(metrics) == 12
        vol_metric = repo.get_metric("gross_transaction_volume")
        assert vol_metric is not None
        assert vol_metric.source_model == "fct_transactions"
        assert "transaction_amount_eur" in vol_metric.relevant_columns


def test_failed_metadata_run_does_not_demote_latest() -> None:
    """Verify that persisting a failed run (is_latest=False) preserves the active latest catalog."""
    target_dir = Path("packages/data_platform/dbt_analytics/target")
    if not (target_dir / "manifest.json").exists():
        pytest.skip("dbt target artifacts not found.")

    with get_test_postgres_connection() as conn:
        repo = MetadataRepository(conn)
        active_latest = repo.get_latest_artifact_run(environment="test")
        assert active_latest is not None

        # Create a failed artifact run snapshot
        failed_run = ArtifactRun(
            run_id="run_failed_test_999",
            environment="test",
            created_at=datetime.now(UTC),
            dbt_version="1.8.0",
            adapter_type="postgres",
            target_name="test",
            database_name="analytics_platform_test",
            schema_name="analytics",
            total_models=0,
            total_sources=0,
            total_tests=0,
            build_status="FAILED",
            artifact_path="/tmp/failed",
            is_latest=False,
        )
        failed_snapshot = MetadataSnapshot(
            artifact_run=failed_run,
            models={},
            sources={},
            metrics={},
            edges=[],
        )

        repo.save_snapshot(failed_snapshot)

        # Confirm that active_latest still remains latest
        latest_after_failure = repo.get_latest_artifact_run(environment="test")
        assert latest_after_failure is not None
        assert latest_after_failure.run_id == active_latest.run_id
        assert latest_after_failure.run_id != "run_failed_test_999"
