"""Integration tests for PostgreSQL schema initialization, COPY ingestion, idempotency, and reconciliation."""

import os
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from data_platform.generator.config import GeneratorConfig
from data_platform.generator.generator import SyntheticDataGenerator
from data_platform.ingestion.ddl import init_database_schemas, truncate_raw_tables
from data_platform.ingestion.pipeline import IngestionPipeline
from shared.config import Settings
from shared.db import get_postgres_connection


@pytest.fixture
def pg_conn() -> psycopg.Connection:
    """Provide a PostgreSQL connection for integration testing, skipping if unreachable locally."""
    settings = Settings()
    try:
        with get_postgres_connection(settings) as conn:
            yield conn
    except psycopg.OperationalError as exc:
        if os.getenv("CI") == "true" or settings.app_env == "testing":
            pytest.fail(f"PostgreSQL connection failed in CI/testing environment: {exc}")
        pytest.skip(f"PostgreSQL container not accessible: {exc}")


def test_schema_initialization(pg_conn: psycopg.Connection) -> None:
    """Verify raw and staging schemas and tables are created idempotently."""
    init_database_schemas(pg_conn)

    with pg_conn.cursor() as cur:
        # Check raw tables exist
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'raw'
            ORDER BY table_name;
        """)
        raw_tables = {row[0] for row in cur.fetchall()}
        expected_raw = {
            "accounts",
            "customers",
            "fee_assessments",
            "fee_collections",
            "fx_rates",
            "gl_accounts",
            "ingestion_batch_manifests",
            "journals",
            "ledger_entries",
            "overdraft_facilities",
            "revenue_recognitions",
            "transactions",
        }
        assert expected_raw.issubset(raw_tables)


def test_batch_ingestion_and_reconciliation(pg_conn: psycopg.Connection) -> None:
    """Verify end-to-end ingestion of a TEST batch and data quality reconciliation."""
    init_database_schemas(pg_conn)
    truncate_raw_tables(pg_conn)

    config = GeneratorConfig.get_profile("TEST", seed=42, reporting_base_currency="EUR")
    generator = SyntheticDataGenerator(config=config)
    batch_data = generator.generate_batch()

    pipeline = IngestionPipeline(pg_conn)
    report = pipeline.ingest_batch(batch_data=batch_data, run_reconciliation=True)

    assert report is not None
    assert report.passed is True
    assert report.total_checks == 7

    for check in report.checks:
        assert check.passed is True, f"Check failed: {check.check_name} - {check.details}"

    # Verify rows exist in raw tables
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw.customers;")
        assert cur.fetchone()[0] == len(batch_data.customers)

        cur.execute("SELECT COUNT(*) FROM raw.transactions;")
        assert cur.fetchone()[0] == len(batch_data.transactions)

        cur.execute("SELECT COUNT(*) FROM raw.journals;")
        assert cur.fetchone()[0] == len(batch_data.journals)


def test_ingestion_idempotency_on_duplicate_run(pg_conn: psycopg.Connection) -> None:
    """Verify running the same batch twice does not duplicate records or cause errors."""
    config = GeneratorConfig.get_profile("TEST", seed=42, reporting_base_currency="EUR")
    generator = SyntheticDataGenerator(config=config)
    batch_data = generator.generate_batch()

    pipeline = IngestionPipeline(pg_conn)

    # First run
    pipeline.ingest_batch(batch_data=batch_data, run_reconciliation=False)

    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw.transactions;")
        txns_run_1 = cur.fetchone()[0]

    # Second duplicate run
    pipeline.ingest_batch(batch_data=batch_data, run_reconciliation=False)

    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw.transactions;")
        txns_run_2 = cur.fetchone()[0]

    assert txns_run_1 == txns_run_2, "Duplicate ingestion must not increase row count"


def test_transaction_rollback_on_failure(pg_conn: psycopg.Connection) -> None:
    """Verify an error during ingestion rolls back the transaction cleanly."""
    config = GeneratorConfig.get_profile("TEST", seed=99, reporting_base_currency="EUR")
    generator = SyntheticDataGenerator(config=config)
    batch_data = generator.generate_batch()

    pipeline = IngestionPipeline(pg_conn)

    # Intentionally corrupt a journal transaction_id to trigger a mock failure
    # by introducing an invalid type/value
    batch_data.journals = []  # Empty journals while ledger entries exist referencing journals!

    # This should fail foreign key / merge constraint when ledger_entries reference missing journals
    # Actually ledger_entries in raw have FK to raw.journals
    # Let's create an invalid ledger entry referencing a nonexistent journal
    from datetime import UTC, datetime

    from data_platform.generator.schemas import LedgerEntryRecord

    now = datetime.now(UTC)
    invalid_entry = LedgerEntryRecord(
        entry_id=f"LE_CORRUPT_{uuid4().hex[:8]}",
        journal_id="NON_EXISTENT_JOURNAL_ID_12345",
        transaction_id=None,
        account_id="ACC_001",
        account_type_marker="CUSTOMER",
        gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
        entry_type="DEBIT",
        amount=Decimal("100.0000"),
        currency="EUR",
        posted_at=now,
    )
    batch_data.ledger_entries.append(invalid_entry)

    with pytest.raises(RuntimeError, match="failed and was rolled back"):
        pipeline.ingest_batch(batch_data=batch_data, run_reconciliation=False)

    # Verify that the corrupt entry was not persisted
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.ledger_entries WHERE entry_id = %s;",
            (invalid_entry.entry_id,),
        )
        assert cur.fetchone()[0] == 0
