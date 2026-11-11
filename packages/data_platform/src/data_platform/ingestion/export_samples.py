"""Reproducible exporter for synthetic raw database tables and dbt analytical outputs."""

import csv
from pathlib import Path

import psycopg
from shared.config import get_settings
from shared.db import get_postgres_connection

REPO_ROOT = Path(__file__).resolve().parents[5]
SAMPLE_DATA_DIR = REPO_ROOT / "sample_data"

RAW_EXPORTS: dict[str, str] = {
    "gl_accounts.csv": "SELECT * FROM raw.gl_accounts ORDER BY gl_account_id",
    "customers.csv": "SELECT * FROM raw.customers ORDER BY customer_id",
    "accounts.csv": "SELECT * FROM raw.accounts ORDER BY account_id",
    "overdraft_facilities.csv": "SELECT * FROM raw.overdraft_facilities ORDER BY facility_id",
    "fx_rates.csv": (
        "SELECT * FROM raw.fx_rates "
        "WHERE rate_date BETWEEN '2025-01-01' AND '2025-01-15' "
        "ORDER BY rate_date, from_currency, to_currency"
    ),
    "transactions.csv": "SELECT * FROM raw.transactions ORDER BY transaction_id",
    "journals.csv": "SELECT * FROM raw.journals ORDER BY journal_id",
    "ledger_entries.csv": "SELECT * FROM raw.ledger_entries ORDER BY entry_id",
    "fee_assessments.csv": "SELECT * FROM raw.fee_assessments ORDER BY assessment_id",
    "fee_collections.csv": "SELECT * FROM raw.fee_collections ORDER BY collection_id",
    "revenue_recognitions.csv": "SELECT * FROM raw.revenue_recognitions ORDER BY recognition_id",
    "ingestion_batch_manifests.csv": "SELECT * FROM raw.ingestion_batch_manifests ORDER BY started_at",
}

ANALYTICAL_EXPORTS: dict[str, str] = {
    "dim_customers.csv": "SELECT * FROM analytics.dim_customers ORDER BY customer_id",
    "dim_accounts.csv": "SELECT * FROM analytics.dim_accounts ORDER BY account_id",
    "fct_fee_collections.csv": (
        "SELECT * FROM analytics.fct_fee_collections ORDER BY collection_id"
    ),
    "customer_revenue.csv": (
        "SELECT * FROM analytics.fct_customer_revenue "
        "ORDER BY reporting_month, customer_id, currency, revenue_category"
    ),
    "fee_assessments_analytics.csv": (
        "SELECT * FROM analytics.fct_fee_assessments ORDER BY assessment_id"
    ),
    "transaction_analytics.csv": (
        "SELECT * FROM analytics.fct_transactions ORDER BY transaction_id"
    ),
    "revenue_by_segment.csv": (
        "SELECT "
        "  customer_segment, "
        "  currency, "
        "  COUNT(DISTINCT customer_id) AS customer_count, "
        "  SUM(assessment_count) AS assessment_count, "
        "  SUM(gross_assessed_fee_amount) AS gross_assessed_native, "
        "  SUM(waived_fee_amount) AS waived_native, "
        "  SUM(net_collectible_fee_amount) AS net_collectible_native, "
        "  SUM(collected_fee_amount) AS collected_native, "
        "  SUM(outstanding_fee_amount) AS outstanding_native, "
        "  SUM(net_recognized_revenue) AS net_revenue_native, "
        "  SUM(gross_assessed_fee_amount_eur) AS gross_assessed_eur, "
        "  SUM(waived_fee_amount_eur) AS waived_eur, "
        "  SUM(net_collectible_fee_amount_eur) AS net_collectible_eur, "
        "  SUM(collected_fee_amount_eur) AS collected_eur, "
        "  SUM(outstanding_fee_amount_eur) AS outstanding_eur, "
        "  SUM(net_recognized_revenue_eur) AS net_recognized_revenue_eur "
        "FROM analytics.fct_customer_revenue "
        "GROUP BY customer_segment, currency "
        "ORDER BY customer_segment, currency"
    ),
}


def export_query_to_csv(conn: psycopg.Connection, query: str, output_path: Path) -> int:
    """Execute a read-only SQL query and write the result set to a CSV file with headers."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with conn.cursor() as cur:
        cur.execute(query)
        headers = [desc.name for desc in cur.description or []]
        rows = cur.fetchall()

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    return len(rows)


def export_all_samples(output_dir: Path = SAMPLE_DATA_DIR) -> dict[str, int]:
    """Export all raw and analytical sample CSVs from PostgreSQL."""
    settings = get_settings()
    counts: dict[str, int] = {}

    with get_postgres_connection(settings) as conn:
        for filename, query in RAW_EXPORTS.items():
            counts[filename] = export_query_to_csv(conn, query, output_dir / filename)

        for filename, query in ANALYTICAL_EXPORTS.items():
            counts[filename] = export_query_to_csv(conn, query, output_dir / filename)

    return counts


if __name__ == "__main__":
    results = export_all_samples()
    for name, row_count in results.items():
        print(f"Exported {name}: {row_count} rows")
