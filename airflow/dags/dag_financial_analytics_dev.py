"""Airflow DAG: Governed Daily Financial Analytics Pipeline (DEV Profile).

Orchestrates the end-to-end ingestion, dbt transformations, accounting reconciliation,
and sample exports for the Financial Services Analytics & AI Platform.
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
from data_platform.ingestion.export_samples import export_all_samples
from data_platform.ingestion.reconciler import DataReconciler
from data_platform.ingestion.run import run_ingestion
from data_platform.metadata.repository import MetadataRepository
from data_platform.metadata.service import MetadataService
from shared.config import Settings
from shared.db import get_postgres_connection

from airflow import DAG

logger = logging.getLogger("airflow.task")

PROJECT_DIR = Path("/opt/airflow/project")
DBT_PROJECT_DIR = PROJECT_DIR / "packages/data_platform/dbt_analytics"
PROFILES_DIR = Path("/tmp/dbt_profiles")
SAMPLE_DATA_DIR = PROJECT_DIR / "sample_data"
EXPECTED_DB_NAME = "analytics_platform"


def task_failure_alert(context: dict[str, Any]) -> None:
    """Structured callback invoked on task failure."""
    ti = context.get("task_instance")
    task_id = ti.task_id if ti else "unknown"
    dag_id = ti.dag_id if ti else "unknown"
    execution_date = context.get("logical_date") or context.get("execution_date")
    exception = context.get("exception")

    logger.error(
        "PIPELINE ALERT: Task failed in DAG '%s' | Task: '%s' | Execution: %s | Error: %s",
        dag_id,
        task_id,
        execution_date,
        exception,
    )


def validate_preflight(**context: Any) -> dict[str, Any]:
    """Execute pre-flight checks verifying database identity, credentials and schemas.

    Strictly enforces that the target database is 'analytics_platform' and never
    the test database or unconfigured default.
    """
    settings = Settings()
    logger.info("Connecting to PostgreSQL at %s:%s", settings.postgres_host, settings.postgres_port)

    with get_postgres_connection(settings) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, version();")
        row = cur.fetchone()
        if not row:
            raise AirflowException("Failed to query database metadata.")

        current_db, current_user, pg_version = row[0], row[1], row[2]
        logger.info(
            "Connected to database: '%s' as user: '%s' (PostgreSQL: %s)",
            current_db,
            current_user,
            pg_version,
        )

        if current_db != EXPECTED_DB_NAME:
            raise AirflowException(
                f"CRITICAL SAFETY VIOLATION: Pipeline expected database '{EXPECTED_DB_NAME}', "
                f"but connected to '{current_db}'! Execution halted."
            )

        # Ensure required schemas exist
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS analytics;")
        conn.commit()

        # Inspect existing table counts
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw';")
        raw_tables = [r[0] for r in cur.fetchall()]
        logger.info("Discovered %d existing raw tables in '%s'", len(raw_tables), current_db)

    # Generate dbt profile before running subsequent tasks
    profile_path = write_dbt_profile(PROFILES_DIR)
    logger.info("Generated dbt profile at: %s", profile_path)

    metadata = {
        "database": current_db,
        "user": current_user,
        "raw_table_count": len(raw_tables),
        "preflight_status": "PASSED",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return metadata


def ingest_dev_dataset(**context: Any) -> dict[str, Any]:
    """Run deterministic synthetic data ingestion for DEV profile (seed 42).

    Uses idempotent ON CONFLICT DO NOTHING to preserve data without duplicates.
    """
    settings = Settings()
    logger.info("Triggering DEV synthetic ingestion on database: %s", settings.postgres_db)

    exit_code = run_ingestion(
        profile="DEV",
        seed=42,
        reporting_base_currency="EUR",
        reset=False,
        settings=settings,
    )

    if exit_code != 0:
        raise AirflowException(f"DEV data ingestion failed with non-zero exit code: {exit_code}")

    return {
        "status": "SUCCESS",
        "profile": "DEV",
        "seed": 42,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def reconcile_financial_integrity(**context: Any) -> dict[str, Any]:
    """Run comprehensive accounting and data quality reconciliation suite."""
    settings = Settings()
    with get_postgres_connection(settings) as conn:
        reconciler = DataReconciler(conn)
        report = reconciler.run_reconciliation(batch_id="airflow_scheduled_run")

        logger.info(
            "Reconciliation Suite: %d checks evaluated. Passed: %s",
            report.total_checks,
            report.passed,
        )

        for check in report.checks:
            status = "PASSED" if check.passed else "FAILED"
            logger.info("  [%s] %s: %s", status, check.check_name, check.details)

        if not report.passed:
            failed = [c.check_name for c in report.checks if not c.passed]
            raise AirflowException(
                f"Financial reconciliation failed! Failed checks: {', '.join(failed)}"
            )

        row_counts = report.summary_metrics.get("row_counts", {})
        return {
            "reconciliation_passed": report.passed,
            "total_checks": report.total_checks,
            "row_counts": row_counts,
        }


def publish_and_load_metadata(**context: Any) -> dict[str, Any]:
    """Publish dbt compilation artifacts and persist metadata catalog to PostgreSQL."""
    service = MetadataService()
    target_dir = DBT_PROJECT_DIR / "target"
    artifacts_root = PROJECT_DIR / "artifacts/dbt"

    run = service.publish_and_load(
        target_dir=target_dir,
        artifacts_root=artifacts_root,
        environment="dev",
    )
    logger.info("Published metadata run: %s", run.run_id)
    return {
        "run_id": run.run_id,
        "total_models": run.total_models,
        "total_sources": run.total_sources,
        "total_tests": run.total_tests,
        "artifact_path": run.artifact_path,
    }


def validate_metadata_catalog(**context: Any) -> dict[str, Any]:
    """Validate that the persisted metadata catalog satisfies governance constraints."""
    settings = Settings()
    with get_postgres_connection(settings) as conn:
        repo = MetadataRepository(conn)
        latest_run = repo.get_latest_artifact_run(environment="dev")
        if not latest_run:
            raise AirflowException("No latest artifact run found in metadata catalog.")

        queryable_models = repo.list_queryable_models()
        if len(queryable_models) < 9:
            raise AirflowException(
                f"Expected at least 9 queryable marts, found {len(queryable_models)}"
            )

        metrics = repo.list_metrics()
        if len(metrics) < 12:
            raise AirflowException(f"Expected at least 12 governed metrics, found {len(metrics)}")

        logger.info(
            "Metadata Catalog Validation Passed: %d models, %d sources, %d tests, %d queryable marts, %d metrics",
            latest_run.total_models,
            latest_run.total_sources,
            latest_run.total_tests,
            len(queryable_models),
            len(metrics),
        )
        return {
            "status": "PASSED",
            "run_id": latest_run.run_id,
            "models_count": latest_run.total_models,
            "queryable_marts_count": len(queryable_models),
            "metrics_count": len(metrics),
        }


def export_sample_artifacts(**context: Any) -> dict[str, Any]:
    """Export fresh sample data CSV files for public portfolio inspection."""
    SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts = export_all_samples(output_dir=SAMPLE_DATA_DIR)
    logger.info("Sample exports completed. Files and row counts:")
    for filename, count in counts.items():
        logger.info("  - %s: %d rows", filename, count)

    return {"exported_files_count": len(counts), "files": counts}


def log_pipeline_completion(**context: Any) -> None:
    """Consolidate pipeline execution telemetry into a structured log."""
    ti = context.get("task_instance")
    if not ti:
        return

    preflight = ti.xcom_pull(task_ids="validate_preflight")
    ingest = ti.xcom_pull(task_ids="ingest_dev_dataset")
    reconciliation = ti.xcom_pull(task_ids="reconcile_financial_integrity")
    exports = ti.xcom_pull(task_ids="export_sample_artifacts")

    logger.info("==================================================================")
    logger.info("FINANCIAL ANALYTICS PIPELINE EXECUTION SUMMARY")
    logger.info("==================================================================")
    logger.info("Status: SUCCESSFUL")
    logger.info("Target Database: %s", preflight.get("database") if preflight else "unknown")
    logger.info("Ingestion Profile: %s", ingest.get("profile") if ingest else "unknown")
    logger.info(
        "Reconciliation Checks: %s passed",
        reconciliation.get("total_checks") if reconciliation else "unknown",
    )
    logger.info(
        "Exported Sample Files: %s", exports.get("exported_files_count") if exports else "unknown"
    )
    logger.info("Completed at: %s", datetime.now(UTC).isoformat())
    logger.info("==================================================================")


default_args = {
    "owner": "analytics_engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(minutes=15),
    "on_failure_callback": task_failure_alert,
}

with DAG(
    dag_id="financial_analytics_dev_pipeline",
    default_args=default_args,
    description="Governed financial analytics pipeline: ingestion, dbt build, reconciliation, and sample export",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["finance", "analytics", "dbt", "dev"],
) as dag:
    preflight_check = PythonOperator(
        task_id="validate_preflight",
        python_callable=validate_preflight,
    )

    ingest_task = PythonOperator(
        task_id="ingest_dev_dataset",
        python_callable=ingest_dev_dataset,
    )

    dbt_build_task = BashOperator(
        task_id="dbt_build_analytics",
        bash_command=(
            'export PATH="/home/airflow/.local/bin:$PATH" && '
            "python -m data_platform.dbt_setup --profiles-dir /tmp/dbt_profiles && "
            "dbt build --profiles-dir /tmp/dbt_profiles "
            "--project-dir /opt/airflow/project/packages/data_platform/dbt_analytics "
            "--target dev"
        ),
    )

    dbt_docs_task = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=(
            'export PATH="/home/airflow/.local/bin:$PATH" && '
            "dbt docs generate --profiles-dir /tmp/dbt_profiles "
            "--project-dir /opt/airflow/project/packages/data_platform/dbt_analytics "
            "--target dev"
        ),
    )

    publish_metadata_task = PythonOperator(
        task_id="publish_and_load_metadata",
        python_callable=publish_and_load_metadata,
    )

    validate_metadata_task = PythonOperator(
        task_id="validate_metadata_catalog",
        python_callable=validate_metadata_catalog,
    )

    reconcile_task = PythonOperator(
        task_id="reconcile_financial_integrity",
        python_callable=reconcile_financial_integrity,
    )

    export_task = PythonOperator(
        task_id="export_sample_artifacts",
        python_callable=export_sample_artifacts,
    )

    completion_task = PythonOperator(
        task_id="log_pipeline_completion",
        python_callable=log_pipeline_completion,
    )

    # Define DAG linear dependency chain
    (
        preflight_check
        >> ingest_task
        >> dbt_build_task
        >> dbt_docs_task
        >> publish_metadata_task
        >> validate_metadata_task
        >> reconcile_task
        >> export_task
        >> completion_task
    )
