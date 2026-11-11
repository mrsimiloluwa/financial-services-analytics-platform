"""Airflow DAG: Isolated Automated Test Pipeline (TEST Profile).

Executes end-to-end analytics validation strictly against the isolated
'analytics_platform_test' database, ensuring zero contamination of development data.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from airflow.exceptions import AirflowException
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from data_platform.dbt_setup import write_dbt_profile
from data_platform.ingestion.reconciler import DataReconciler
from data_platform.ingestion.run import run_ingestion
from data_platform.metadata.repository import MetadataRepository
from data_platform.metadata.service import MetadataService
from shared.config import Settings
from shared.db import ensure_test_database_exists, get_postgres_connection

from airflow import DAG

logger = logging.getLogger("airflow.task")

PROJECT_DIR = Path("/opt/airflow/project")
DBT_PROJECT_DIR = PROJECT_DIR / "packages/data_platform/dbt_analytics"
PROFILES_DIR = Path("/tmp/dbt_profiles")
EXPECTED_TEST_DB = "analytics_platform_test"


def validate_test_preflight(**context: Any) -> dict[str, Any]:
    """Validate test preflight conditions and database isolation."""
    # Ensure test database exists
    base_settings = Settings()
    ensure_test_database_exists(base_settings)

    test_settings = Settings(postgres_db=EXPECTED_TEST_DB)
    logger.info(
        "Connecting to test PostgreSQL at %s:%s/%s",
        test_settings.postgres_host,
        test_settings.postgres_port,
        test_settings.postgres_db,
    )

    with get_postgres_connection(test_settings) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, version();")
        row = cur.fetchone()
        if not row:
            raise AirflowException("Failed to query test database metadata.")

        current_db, current_user = row[0], row[1]
        logger.info("Connected to test database: '%s' as user: '%s'", current_db, current_user)

        if current_db != EXPECTED_TEST_DB:
            raise AirflowException(
                f"TEST ISOLATION VIOLATION: Expected test database '{EXPECTED_TEST_DB}', "
                f"but connected to '{current_db}'! Execution halted."
            )

        # Ensure required schemas exist in test DB
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS analytics;")
        conn.commit()

    # Generate dbt profile with test output
    profile_path = write_dbt_profile(PROFILES_DIR)
    logger.info("Generated dbt profile at: %s", profile_path)

    return {
        "database": current_db,
        "status": "PASSED",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def ingest_test_dataset(**context: Any) -> dict[str, Any]:
    """Ingest deterministic TEST profile dataset into isolated test database."""
    test_settings = Settings(postgres_db=EXPECTED_TEST_DB)
    logger.info("Triggering TEST synthetic ingestion on database: %s", test_settings.postgres_db)

    exit_code = run_ingestion(
        profile="TEST",
        seed=42,
        reporting_base_currency="EUR",
        reset=False,
        settings=test_settings,
    )

    if exit_code != 0:
        raise AirflowException(f"TEST data ingestion failed with non-zero exit code: {exit_code}")

    return {
        "status": "SUCCESS",
        "profile": "TEST",
        "target_db": EXPECTED_TEST_DB,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def reconcile_test_integrity(**context: Any) -> dict[str, Any]:
    """Run reconciliation checks on isolated test database."""
    test_settings = Settings(postgres_db=EXPECTED_TEST_DB)
    with get_postgres_connection(test_settings) as conn:
        reconciler = DataReconciler(conn)
        report = reconciler.run_reconciliation(batch_id="airflow_test_run")

        logger.info(
            "Test DB Reconciliation Suite: %d checks evaluated. Passed: %s",
            report.total_checks,
            report.passed,
        )

        for check in report.checks:
            status = "PASSED" if check.passed else "FAILED"
            logger.info("  [%s] %s: %s", status, check.check_name, check.details)

        if not report.passed:
            failed = [c.check_name for c in report.checks if not c.passed]
            raise AirflowException(
                f"Test DB reconciliation failed! Failed checks: {', '.join(failed)}"
            )

        return {
            "reconciliation_passed": report.passed,
            "total_checks": report.total_checks,
            "target_db": EXPECTED_TEST_DB,
        }


def publish_and_load_test_metadata(**context: Any) -> dict[str, Any]:
    """Publish dbt compilation artifacts and persist metadata catalog to test database."""
    test_settings = Settings(postgres_db=EXPECTED_TEST_DB)
    with get_postgres_connection(test_settings) as conn:
        service = MetadataService(conn=conn)
        target_dir = DBT_PROJECT_DIR / "target"
        artifacts_root = PROJECT_DIR / "artifacts/dbt"

        run = service.publish_and_load(
            target_dir=target_dir,
            artifacts_root=artifacts_root,
            environment="test",
        )
        logger.info("Published TEST metadata run: %s", run.run_id)
        return {
            "run_id": run.run_id,
            "environment": "test",
            "total_models": run.total_models,
            "total_sources": run.total_sources,
            "total_tests": run.total_tests,
            "target_db": EXPECTED_TEST_DB,
        }


def validate_test_metadata_catalog(**context: Any) -> dict[str, Any]:
    """Validate that the persisted TEST metadata catalog satisfies governance constraints."""
    test_settings = Settings(postgres_db=EXPECTED_TEST_DB)
    with get_postgres_connection(test_settings) as conn:
        repo = MetadataRepository(conn)
        latest_run = repo.get_latest_artifact_run(environment="test")
        if not latest_run:
            raise AirflowException("No latest artifact run found in TEST metadata catalog.")

        queryable_models = repo.list_queryable_models()
        if len(queryable_models) < 9:
            raise AirflowException(
                f"Expected at least 9 queryable marts, found {len(queryable_models)}"
            )

        metrics = repo.list_metrics()
        if len(metrics) < 12:
            raise AirflowException(f"Expected at least 12 governed metrics, found {len(metrics)}")

        logger.info(
            "TEST Metadata Catalog Validation Passed: %d models, %d queryable marts, %d metrics",
            latest_run.total_models,
            len(queryable_models),
            len(metrics),
        )
        return {
            "status": "PASSED",
            "run_id": latest_run.run_id,
            "environment": "test",
            "target_db": EXPECTED_TEST_DB,
            "models_count": latest_run.total_models,
            "queryable_marts_count": len(queryable_models),
            "metrics_count": len(metrics),
        }


default_args = {
    "owner": "analytics_engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
    "execution_timeout": timedelta(minutes=10),
}

with DAG(
    dag_id="financial_analytics_test_pipeline",
    default_args=default_args,
    description="Automated analytics test pipeline targeting isolated analytics_platform_test",
    schedule_interval=None,  # Manual or CI trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["finance", "test", "dbt", "isolated"],
) as dag:
    preflight_test = PythonOperator(
        task_id="validate_test_preflight",
        python_callable=validate_test_preflight,
    )

    ingest_test = PythonOperator(
        task_id="ingest_test_dataset",
        python_callable=ingest_test_dataset,
    )

    dbt_build_test = BashOperator(
        task_id="dbt_build_test_analytics",
        bash_command=(
            'export PATH="/home/airflow/.local/bin:$PATH" && '
            "python -m data_platform.dbt_setup --profiles-dir /tmp/dbt_profiles && "
            "dbt build --profiles-dir /tmp/dbt_profiles "
            "--project-dir /opt/airflow/project/packages/data_platform/dbt_analytics "
            "--target test"
        ),
    )

    dbt_docs_test = BashOperator(
        task_id="dbt_docs_generate_test",
        bash_command=(
            'export PATH="/home/airflow/.local/bin:$PATH" && '
            "dbt docs generate --profiles-dir /tmp/dbt_profiles "
            "--project-dir /opt/airflow/project/packages/data_platform/dbt_analytics "
            "--target test"
        ),
    )

    publish_metadata_test = PythonOperator(
        task_id="publish_and_load_test_metadata",
        python_callable=publish_and_load_test_metadata,
    )

    validate_metadata_test = PythonOperator(
        task_id="validate_test_metadata_catalog",
        python_callable=validate_test_metadata_catalog,
    )

    reconcile_test = PythonOperator(
        task_id="reconcile_test_integrity",
        python_callable=reconcile_test_integrity,
    )

    (
        preflight_test
        >> ingest_test
        >> dbt_build_test
        >> dbt_docs_test
        >> publish_metadata_test
        >> validate_metadata_test
        >> reconcile_test
    )
