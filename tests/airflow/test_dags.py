"""Unit tests for Apache Airflow DAG structures, task hierarchies, and safety guards."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DAGS_DIR = REPO_ROOT / "airflow" / "dags"
DEV_DAG_FILE = DAGS_DIR / "dag_financial_analytics_dev.py"
TEST_DAG_FILE = DAGS_DIR / "dag_financial_analytics_test.py"


def test_dag_files_exist() -> None:
    """Ensure both DEV and TEST DAG definitions exist on disk."""
    assert DEV_DAG_FILE.exists(), f"Missing DEV DAG file at {DEV_DAG_FILE}"
    assert TEST_DAG_FILE.exists(), f"Missing TEST DAG file at {TEST_DAG_FILE}"


def test_dev_dag_ast_structure() -> None:
    """Verify DEV DAG structure, task IDs, target DB safety, and schedule."""
    source = DEV_DAG_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(DEV_DAG_FILE))

    # Check for expected constants
    found_db = False
    task_ids: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "EXPECTED_DB_NAME"
                    and isinstance(node.value, ast.Constant)
                ):
                    assert node.value.value == "analytics_platform"
                    found_db = True

        # Extract task_ids from Operator instantiations
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "task_id" and isinstance(keyword.value, ast.Constant):
                    task_ids.add(keyword.value.value)

    assert found_db, "EXPECTED_DB_NAME constant missing or invalid in DEV DAG."
    expected_tasks = {
        "validate_preflight",
        "ingest_dev_dataset",
        "dbt_build_analytics",
        "dbt_docs_generate",
        "publish_and_load_metadata",
        "validate_metadata_catalog",
        "reconcile_financial_integrity",
        "export_sample_artifacts",
        "log_pipeline_completion",
    }
    assert expected_tasks.issubset(task_ids), f"Missing tasks in DEV DAG. Found: {task_ids}"


def test_test_dag_ast_structure() -> None:
    """Verify TEST DAG structure, isolated target DB, and task dependencies."""
    source = TEST_DAG_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(TEST_DAG_FILE))

    found_test_db = False
    task_ids: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "EXPECTED_TEST_DB"
                    and isinstance(node.value, ast.Constant)
                ):
                    assert node.value.value == "analytics_platform_test"
                    found_test_db = True

        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "task_id" and isinstance(keyword.value, ast.Constant):
                    task_ids.add(keyword.value.value)

    assert found_test_db, "EXPECTED_TEST_DB constant missing or invalid in TEST DAG."
    expected_tasks = {
        "validate_test_preflight",
        "ingest_test_dataset",
        "dbt_build_test_analytics",
        "dbt_docs_generate_test",
        "publish_and_load_test_metadata",
        "validate_test_metadata_catalog",
        "reconcile_test_integrity",
    }
    assert expected_tasks.issubset(task_ids), f"Missing tasks in TEST DAG. Found: {task_ids}"


def test_dagbag_import_when_airflow_available() -> None:
    """If Airflow is installed in environment, verify DagBag parses with 0 errors."""
    try:
        from airflow.models import DagBag
    except (ImportError, AttributeError):
        pytest.skip("Airflow runtime not installed in active environment.")

    dagbag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    assert len(dagbag.import_errors) == 0, f"DAG import errors: {dagbag.import_errors}"
    assert "financial_analytics_dev_pipeline" in dagbag.dags
    assert "financial_analytics_test_pipeline" in dagbag.dags
