"""Data quality and reconciliation validation engine for staged and merged banking records."""

from dataclasses import dataclass, field
from typing import Any

import psycopg


@dataclass
class ReconciliationCheckResult:
    """Outcome of an individual reconciliation check."""

    check_name: str
    passed: bool
    details: str
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReconciliationReport:
    """Consolidated reconciliation and data quality audit report for a batch."""

    batch_id: str
    passed: bool
    total_checks: int
    checks: list[ReconciliationCheckResult] = field(default_factory=list)
    summary_metrics: dict[str, Any] = field(default_factory=dict)


class DataReconciler:
    """Runs rigorous data quality and accounting reconciliation checks against PostgreSQL raw tables."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def run_reconciliation(self, batch_id: str) -> ReconciliationReport:
        """Execute full reconciliation suite and return structured audit report."""
        checks: list[ReconciliationCheckResult] = []

        with self.conn.cursor() as cur:
            # 1. Double-Entry Journal Balancing per Currency Leg
            cur.execute("""
                WITH leg_balances AS (
                    SELECT
                        journal_id,
                        currency,
                        SUM(CASE WHEN entry_type = 'DEBIT' THEN amount ELSE -amount END) AS leg_diff
                    FROM raw.ledger_entries
                    GROUP BY journal_id, currency
                )
                SELECT journal_id, currency, leg_diff
                FROM leg_balances
                WHERE leg_diff <> 0.0000;
            """)
            unbalanced_journals = cur.fetchall()
            jrn_passed = len(unbalanced_journals) == 0
            checks.append(
                ReconciliationCheckResult(
                    check_name="DOUBLE_ENTRY_JOURNAL_BALANCING",
                    passed=jrn_passed,
                    details=(
                        "All journals balance per currency leg"
                        if jrn_passed
                        else f"Found {len(unbalanced_journals)} unbalanced currency legs in journals: {unbalanced_journals[:5]}"
                    ),
                    metrics={"unbalanced_count": len(unbalanced_journals)},
                )
            )

            # 2. No Ledger Postings for Failed or Pending Transactions
            cur.execute("""
                SELECT
                    t.transaction_id,
                    t.status,
                    COUNT(le.entry_id) AS illegal_posting_count
                FROM raw.transactions t
                JOIN raw.ledger_entries le ON t.transaction_id = le.transaction_id
                WHERE t.status IN ('FAILED', 'PENDING')
                GROUP BY t.transaction_id, t.status;
            """)
            illegal_postings = cur.fetchall()
            illegal_passed = len(illegal_postings) == 0
            checks.append(
                ReconciliationCheckResult(
                    check_name="NO_POSTINGS_FOR_UNSETTLED_TXNS",
                    passed=illegal_passed,
                    details=(
                        "No ledger postings exist for FAILED or PENDING transactions"
                        if illegal_passed
                        else f"Found {len(illegal_postings)} unsettled transactions with ledger postings"
                    ),
                    metrics={"illegal_posting_txns": len(illegal_postings)},
                )
            )

            # 3. Customer to Account Referential Integrity
            cur.execute("""
                SELECT COUNT(*)
                FROM raw.accounts a
                LEFT JOIN raw.customers c ON a.customer_id = c.customer_id
                WHERE c.customer_id IS NULL;
            """)
            orphan_accounts = cur.fetchone()[0]
            checks.append(
                ReconciliationCheckResult(
                    check_name="ACCOUNT_CUSTOMER_REFERENTIAL_INTEGRITY",
                    passed=(orphan_accounts == 0),
                    details=f"Orphan accounts without parent customer: {orphan_accounts}",
                    metrics={"orphan_accounts": orphan_accounts},
                )
            )

            # 4. Transaction to Account Referential Integrity
            cur.execute("""
                SELECT COUNT(*)
                FROM raw.transactions t
                LEFT JOIN raw.accounts a ON t.account_id = a.account_id
                WHERE a.account_id IS NULL;
            """)
            orphan_txns = cur.fetchone()[0]
            checks.append(
                ReconciliationCheckResult(
                    check_name="TRANSACTION_ACCOUNT_REFERENTIAL_INTEGRITY",
                    passed=(orphan_txns == 0),
                    details=f"Orphan transactions without valid account: {orphan_txns}",
                    metrics={"orphan_transactions": orphan_txns},
                )
            )

            # 5. Fee Assessment Mathematical Decomposition
            cur.execute("""
                SELECT COUNT(*)
                FROM raw.fee_assessments
                WHERE gross_assessed_amount <> (waived_amount + net_collectible_amount);
            """)
            invalid_assessments = cur.fetchone()[0]
            checks.append(
                ReconciliationCheckResult(
                    check_name="FEE_ASSESSMENT_DECOMPOSITION",
                    passed=(invalid_assessments == 0),
                    details=f"Fee assessments failing gross = waived + net: {invalid_assessments}",
                    metrics={"invalid_assessments": invalid_assessments},
                )
            )

            # 6. Cumulative Fee Collections Ceiling
            cur.execute("""
                WITH coll_totals AS (
                    SELECT
                        assessment_id,
                        SUM(collected_amount) AS total_collected
                    FROM raw.fee_collections
                    WHERE collection_status IN ('SETTLED', 'PARTIAL')
                    GROUP BY assessment_id
                )
                SELECT COUNT(*)
                FROM coll_totals ct
                JOIN raw.fee_assessments fa ON ct.assessment_id = fa.assessment_id
                WHERE ct.total_collected > fa.net_collectible_amount;
            """)
            exceeded_collections = cur.fetchone()[0]
            checks.append(
                ReconciliationCheckResult(
                    check_name="FEE_COLLECTION_CEILING_ENFORCEMENT",
                    passed=(exceeded_collections == 0),
                    details=f"Assessments where collections exceed collectible ceiling: {exceeded_collections}",
                    metrics={"exceeded_collections": exceeded_collections},
                )
            )

            # 7. Currency Domains Validity
            cur.execute("""
                SELECT COUNT(*)
                FROM raw.accounts
                WHERE currency NOT IN ('EUR', 'USD', 'GBP', 'CHF');
            """)
            invalid_currencies = cur.fetchone()[0]
            checks.append(
                ReconciliationCheckResult(
                    check_name="SUPPORTED_CURRENCY_DOMAINS",
                    passed=(invalid_currencies == 0),
                    details=f"Accounts with invalid ISO currencies: {invalid_currencies}",
                    metrics={"invalid_currencies": invalid_currencies},
                )
            )

            # 8. Row Counts Summary
            tables = [
                "gl_accounts",
                "customers",
                "accounts",
                "overdraft_facilities",
                "fx_rates",
                "transactions",
                "journals",
                "ledger_entries",
                "fee_assessments",
                "fee_collections",
                "revenue_recognitions",
                "ingestion_batch_manifests",
            ]
            row_counts: dict[str, int] = {}
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM raw.{t};")
                row_counts[t] = cur.fetchone()[0]

        all_passed = all(c.passed for c in checks)
        return ReconciliationReport(
            batch_id=batch_id,
            passed=all_passed,
            total_checks=len(checks),
            checks=checks,
            summary_metrics={"row_counts": row_counts},
        )
