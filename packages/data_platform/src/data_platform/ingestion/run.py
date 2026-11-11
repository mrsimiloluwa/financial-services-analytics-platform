"""CLI entrypoint to execute end-to-end synthetic data generation and PostgreSQL ingestion."""

import argparse
import sys
from datetime import UTC, datetime

from data_platform.generator.config import GeneratorConfig
from data_platform.generator.generator import SyntheticDataGenerator
from data_platform.ingestion.ddl import truncate_raw_tables
from data_platform.ingestion.pipeline import IngestionPipeline
from shared.config import Settings
from shared.db import get_postgres_connection


def run_ingestion(
    profile: str = "DEV",
    seed: int = 42,
    reporting_base_currency: str = "EUR",
    reset: bool = False,
    settings: Settings | None = None,
    database: str | None = None,
) -> int:
    """Execute end-to-end generation, COPY ingestion, and post-load reconciliation."""
    print(
        f"[{datetime.now(UTC).isoformat()}] Starting ingestion run: profile={profile}, seed={seed}, base_currency={reporting_base_currency}, reset={reset}"
    )

    config = GeneratorConfig.get_profile(
        profile=profile,  # type: ignore[arg-type]
        seed=seed,
        reporting_base_currency=reporting_base_currency,  # type: ignore[arg-type]
    )

    print(f"[{datetime.now(UTC).isoformat()}] Generating synthetic dataset...")
    generator = SyntheticDataGenerator(config=config)
    batch_data = generator.generate_batch()
    print(
        f"[{datetime.now(UTC).isoformat()}] Generated {batch_data.manifest.total_records} records across 11 entities."
    )
    for k, v in batch_data.manifest.entity_counts.items():
        print(f"  - {k}: {v}")

    if settings is not None:
        active_settings = settings
    elif database:
        active_settings = Settings(postgres_db=database)
    else:
        active_settings = Settings()

    print(
        f"[{datetime.now(UTC).isoformat()}] Connecting to PostgreSQL: {active_settings.postgres_host}:{active_settings.postgres_port}/{active_settings.postgres_db}"
    )

    with get_postgres_connection(active_settings) as conn:
        if reset:
            print(
                f"[{datetime.now(UTC).isoformat()}] Reset requested on database '{active_settings.postgres_db}': truncating existing raw tables..."
            )
            truncate_raw_tables(conn, allow_non_test_db=True)

        pipeline = IngestionPipeline(conn)
        report = pipeline.ingest_batch(batch_data=batch_data, run_reconciliation=True)

        if report and report.passed:
            print(
                f"[{datetime.now(UTC).isoformat()}] Ingestion & Reconciliation SUCCESSFUL for batch {batch_data.manifest.batch_id}"
            )
            print(
                f"Total reconciliation checks passed: {report.total_checks}/{report.total_checks}"
            )
            print("PostgreSQL raw row counts:")
            for tbl, count in report.summary_metrics.get("row_counts", {}).items():
                print(f"  - raw.{tbl}: {count}")
            return 0
        else:
            print(f"[{datetime.now(UTC).isoformat()}] Ingestion FAILED reconciliation checks!")
            return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest synthetic banking data into PostgreSQL")
    parser.add_argument(
        "--profile",
        default="TEST",
        choices=["TEST", "DEV", "DEMO"],
        help="Generation volume profile",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic generator seed")
    parser.add_argument(
        "--currency", default="EUR", choices=["EUR", "USD", "GBP"], help="Reporting base currency"
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help="Target PostgreSQL database name",
    )
    parser.add_argument("--reset", action="store_true", help="Truncate raw tables before ingestion")
    args = parser.parse_args()

    sys.exit(
        run_ingestion(
            profile=args.profile,
            seed=args.seed,
            reporting_base_currency=args.currency,
            reset=args.reset,
            database=args.database,
        )
    )
