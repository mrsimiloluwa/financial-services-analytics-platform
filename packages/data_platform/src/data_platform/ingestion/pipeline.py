"""High-performance batch ingestion pipeline using PostgreSQL COPY, staging tables, and transactional merge."""

import json

import psycopg
from data_platform.generator.generator import GeneratedBatchData
from data_platform.ingestion.ddl import (
    init_database_schemas,
    load_sql_file,
    truncate_staging_tables,
)
from data_platform.ingestion.reconciler import DataReconciler, ReconciliationReport


class IngestionPipeline:
    """Manages idempotent batch ingestion from synthetic generator to PostgreSQL raw tables."""

    BATCH_CHUNK_SIZE: int = 5000

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def ingest_batch(
        self,
        batch_data: GeneratedBatchData,
        run_reconciliation: bool = True,
    ) -> ReconciliationReport | None:
        """Execute transactional staged COPY, validation, merge, manifest logging, and reconciliation."""
        init_database_schemas(self.conn)

        try:
            # 1. Truncate staging tables before copy
            truncate_staging_tables(self.conn)

            # 2. Fast Batch COPY into unlogged staging tables
            self._copy_to_staging(batch_data)

            # 3. Transactional Merge from Staging to Raw
            self._merge_staging_to_raw()

            # 4. Record Ingestion Batch Manifest
            self._record_manifest(batch_data)

            # Commit the transaction atomically
            self.conn.commit()

            # 5. Clean up staging tables after commit
            truncate_staging_tables(self.conn)

            # 6. Post-Ingestion Data Quality & Accounting Reconciliation
            if run_reconciliation:
                reconciler = DataReconciler(self.conn)
                report = reconciler.run_reconciliation(str(batch_data.manifest.batch_id))
                if not report.passed:
                    failed = [c.check_name for c in report.checks if not c.passed]
                    raise ValueError(f"Post-ingestion reconciliation failed checks: {failed}")
                return report

            return None

        except Exception as exc:
            self.conn.rollback()
            raise RuntimeError(
                f"Ingestion batch {batch_data.manifest.batch_id} failed and was rolled back: {exc}"
            ) from exc

    def _copy_to_staging(self, data: GeneratedBatchData) -> None:
        """Stream objects into PostgreSQL staging tables via COPY in chunks."""
        with self.conn.cursor() as cur:
            # GL Accounts
            with cur.copy("COPY staging.gl_accounts FROM STDIN") as copy:
                for gl in data.gl_accounts:
                    copy.write_row(
                        (
                            gl.gl_account_id,
                            gl.gl_account_number,
                            gl.account_name,
                            gl.account_category,
                            gl.normal_balance,
                            gl.currency,
                            gl.description,
                        )
                    )

            # Customers
            with cur.copy("COPY staging.customers FROM STDIN") as copy:
                for c in data.customers:
                    copy.write_row(
                        (
                            c.customer_id,
                            c.legal_entity_id,
                            c.customer_name,
                            c.customer_segment,
                            c.status,
                            c.onboarding_date,
                        )
                    )

            # Accounts
            with cur.copy("COPY staging.accounts FROM STDIN") as copy:
                for a in data.accounts:
                    copy.write_row(
                        (
                            a.account_id,
                            a.customer_id,
                            a.account_number,
                            a.account_type,
                            a.currency,
                            a.opening_balance,
                            a.reserved_funds,
                            a.status,
                            a.opened_at,
                        )
                    )

            # Overdraft Facilities
            with cur.copy("COPY staging.overdraft_facilities FROM STDIN") as copy:
                for od in data.overdraft_facilities:
                    copy.write_row(
                        (
                            od.facility_id,
                            od.account_id,
                            od.authorized_limit,
                            od.standard_interest_rate,
                            od.unauthorized_penalty_rate,
                            od.effective_start_date,
                            od.effective_end_date,
                        )
                    )

            # FX Rates
            with cur.copy("COPY staging.fx_rates FROM STDIN") as copy:
                for fx in data.fx_rates:
                    copy.write_row(
                        (
                            fx.rate_id,
                            fx.rate_date,
                            fx.from_currency,
                            fx.to_currency,
                            fx.mid_rate,
                            fx.bid_rate,
                            fx.ask_rate,
                            fx.rate_source,
                            fx.rate_type,
                            fx.rate_timestamp,
                        )
                    )

            # Transactions
            with cur.copy("COPY staging.transactions FROM STDIN") as copy:
                for t in data.transactions:
                    copy.write_row(
                        (
                            t.transaction_id,
                            t.account_id,
                            t.counterparty_account_id,
                            t.transaction_type,
                            t.channel,
                            t.direction,
                            t.transaction_amount,
                            t.transaction_currency,
                            t.settlement_currency,
                            t.customer_fx_rate,
                            t.base_currency_amount,
                            t.status,
                            t.original_transaction_id,
                            t.journal_id,
                            t.initiated_at,
                            t.settled_at,
                        )
                    )

            # Journals
            with cur.copy("COPY staging.journals FROM STDIN") as copy:
                for j in data.journals:
                    copy.write_row(
                        (
                            j.journal_id,
                            j.transaction_id,
                            j.journal_type,
                            j.description,
                            j.created_at,
                        )
                    )

            # Ledger Entries
            with cur.copy("COPY staging.ledger_entries FROM STDIN") as copy:
                for le in data.ledger_entries:
                    copy.write_row(
                        (
                            le.entry_id,
                            le.journal_id,
                            le.transaction_id,
                            le.account_id,
                            le.account_type_marker,
                            le.gl_account_id,
                            le.entry_type,
                            le.amount,
                            le.currency,
                            le.original_entry_id,
                            le.posting_status,
                            le.posted_at,
                        )
                    )

            # Fee Assessments
            with cur.copy("COPY staging.fee_assessments FROM STDIN") as copy:
                for fa in data.fee_assessments:
                    copy.write_row(
                        (
                            fa.assessment_id,
                            fa.transaction_id,
                            fa.account_id,
                            fa.gross_assessed_amount,
                            fa.waived_amount,
                            fa.waiver_reason,
                            fa.net_collectible_amount,
                            fa.assessment_status,
                            fa.assessed_at,
                        )
                    )

            # Fee Collections
            with cur.copy("COPY staging.fee_collections FROM STDIN") as copy:
                for fc in data.fee_collections:
                    copy.write_row(
                        (
                            fc.collection_id,
                            fc.assessment_id,
                            fc.account_id,
                            fc.collection_attempt_number,
                            fc.target_amount,
                            fc.collected_amount,
                            fc.outstanding_amount,
                            fc.collection_status,
                            fc.failure_reason,
                            fc.attempted_at,
                            fc.settled_at,
                            fc.linked_ledger_entry_id,
                        )
                    )

            # Revenue Recognitions
            with cur.copy("COPY staging.revenue_recognitions FROM STDIN") as copy:
                for rr in data.revenue_recognitions:
                    copy.write_row(
                        (
                            rr.recognition_id,
                            rr.collection_id,
                            rr.gross_collected_revenue,
                            rr.reversed_revenue_amount,
                            rr.pass_through_cost,
                            rr.net_recognized_revenue,
                            rr.recognized_at,
                        )
                    )

    def _merge_staging_to_raw(self) -> None:
        """Merge staged data into raw tables transactionally using ON CONFLICT DO NOTHING for idempotency."""
        merge_sql = load_sql_file("merge_staging_to_raw.sql")
        with self.conn.cursor() as cur:
            cur.execute(merge_sql)

    def _record_manifest(self, data: GeneratedBatchData) -> None:
        """Insert batch audit manifest record."""
        m = data.manifest
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.ingestion_batch_manifests (
                    batch_id, generator_version, random_seed, profile_name,
                    reporting_base_currency, total_records, entity_counts,
                    started_at, completed_at, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (batch_id) DO NOTHING;
                """,
                (
                    m.batch_id,
                    m.generator_version,
                    m.random_seed,
                    m.profile_name,
                    m.reporting_base_currency,
                    m.total_records,
                    json.dumps(m.entity_counts),
                    m.started_at,
                    m.completed_at,
                    m.status,
                ),
            )
