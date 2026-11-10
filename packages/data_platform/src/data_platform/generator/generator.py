"""Synthetic data generator orchestrating all banking engines into a unified dataset."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from data_platform.generator.config import STANDARD_GL_ACCOUNTS, GeneratorConfig
from data_platform.generator.engines.account_engine import AccountEngine
from data_platform.generator.engines.customer_engine import CustomerEngine
from data_platform.generator.engines.fee_engine import FeeEngine
from data_platform.generator.engines.fx_engine import FXEngine
from data_platform.generator.engines.ledger_engine import LedgerEngine
from data_platform.generator.engines.transaction_engine import TransactionEngine
from data_platform.generator.schemas import (
    AccountRecord,
    CustomerRecord,
    FeeAssessmentRecord,
    FeeCollectionRecord,
    FXRateRecord,
    GLAccountRecord,
    IngestionBatchManifest,
    JournalRecord,
    LedgerEntryRecord,
    OverdraftFacilityRecord,
    RevenueRecognitionRecord,
    TransactionRecord,
)


@dataclass
class GeneratedBatchData:
    """Complete dataset generated for a simulation batch."""

    manifest: IngestionBatchManifest
    gl_accounts: list[GLAccountRecord] = field(default_factory=list)
    customers: list[CustomerRecord] = field(default_factory=list)
    accounts: list[AccountRecord] = field(default_factory=list)
    overdraft_facilities: list[OverdraftFacilityRecord] = field(default_factory=list)
    fx_rates: list[FXRateRecord] = field(default_factory=list)
    transactions: list[TransactionRecord] = field(default_factory=list)
    journals: list[JournalRecord] = field(default_factory=list)
    ledger_entries: list[LedgerEntryRecord] = field(default_factory=list)
    fee_assessments: list[FeeAssessmentRecord] = field(default_factory=list)
    fee_collections: list[FeeCollectionRecord] = field(default_factory=list)
    revenue_recognitions: list[RevenueRecognitionRecord] = field(default_factory=list)


class SyntheticDataGenerator:
    """Orchestrates all synthetic banking data generation engines deterministically."""

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        self.config = config or GeneratorConfig.get_profile("DEV")

    def generate_batch(self) -> GeneratedBatchData:
        """Execute end-to-end deterministic data generation producing all banking records."""
        start_time = datetime.now(UTC)
        batch_id = uuid4()

        # 1. Master Chart of Accounts
        gl_accounts = [
            GLAccountRecord(
                gl_account_id=g.gl_account_id,
                gl_account_number=g.gl_account_number,
                account_name=g.account_name,
                account_category=g.account_category,
                normal_balance=g.normal_balance,
                currency=g.currency,
                description=g.description,
            )
            for g in STANDARD_GL_ACCOUNTS
        ]

        # 2. Customers & Accounts
        cust_engine = CustomerEngine(seed=self.config.seed)
        customers = cust_engine.generate_customers(count=self.config.customer_count)

        acc_engine = AccountEngine(
            seed=self.config.seed,
            supported_currencies=self.config.supported_account_currencies,
        )
        accounts, overdraft_facilities = acc_engine.generate_accounts_and_facilities(customers)

        # 3. Foreign Exchange Rates
        fx_engine = FXEngine(
            seed=self.config.seed,
            reporting_base_currency=self.config.reporting_base_currency,
            supported_currencies=self.config.supported_account_currencies,
        )
        fx_rates = fx_engine.generate_rates(
            start_date=self.config.start_date,
            end_date=self.config.end_date,
        )

        # 4. Transactions and Double-Entry Settlement Journals
        ledger_engine = LedgerEngine(fx_engine=fx_engine)
        txn_engine = TransactionEngine(
            config=self.config,
            fx_engine=fx_engine,
            ledger_engine=ledger_engine,
        )
        transactions, journals, ledger_entries = txn_engine.generate_transactions_and_journals(
            customers=customers,
            accounts=accounts,
        )

        # 5. Fee Assessments, Collections, and Fee Accounting Journals
        account_map = {a.account_id: a for a in accounts}
        customer_map = {c.customer_id: c for c in customers}
        fee_engine = FeeEngine(ledger_engine=ledger_engine)

        fee_assessments: list[FeeAssessmentRecord] = []
        fee_collections: list[FeeCollectionRecord] = []
        revenue_recognitions: list[RevenueRecognitionRecord] = []

        # Assess fees for settled transactions
        for txn in transactions:
            if txn.status != "SETTLED":
                continue

            src_acc = account_map.get(txn.account_id)
            if not src_acc:
                continue

            cust = customer_map.get(src_acc.customer_id)
            seg = cust.customer_segment if cust else None

            # Apply waivers: 10% of transactions receive promotional/tier waiver
            waiver_pct = Decimal("0.0000")
            reason: str | None = None
            if (hash(txn.transaction_id) % 10) == 0:
                waiver_pct = Decimal("0.1500")
                reason = "VOLUME_TIER_CONCESSION"

            assessment = fee_engine.assess_fee(
                transaction=txn,
                customer_segment=seg,
                waiver_percentage=waiver_pct,
                waiver_reason=reason,
            )
            if not assessment or assessment.net_collectible_amount == Decimal("0.0000"):
                continue

            fee_assessments.append(assessment)

            # Attempt collection sweep (occasional failure e.g. 5% failure rate for test realism)
            force_fail = (hash(txn.transaction_id) % 20) == 0
            fail_reason = "INSUFFICIENT_FUNDS" if force_fail else None

            # Assume 5% network pass-through cost
            pass_through = (assessment.net_collectible_amount * Decimal("0.0500")).quantize(
                Decimal("0.0001")
            )

            collection_rec, fee_jrn, rev_rec = fee_engine.execute_collection_attempt(
                assessment=assessment,
                account=src_acc,
                attempt_number=1,
                force_fail=force_fail,
                failure_reason=fail_reason,
                pass_through_cost=pass_through,
                transaction_type=txn.transaction_type,
            )
            fee_collections.append(collection_rec)

            if fee_jrn:
                journals.append(fee_jrn)
                ledger_entries.extend(fee_jrn.entries)
            if rev_rec:
                revenue_recognitions.append(rev_rec)

        completed_time = datetime.now(UTC)

        entity_counts = {
            "gl_accounts": len(gl_accounts),
            "customers": len(customers),
            "accounts": len(accounts),
            "overdraft_facilities": len(overdraft_facilities),
            "fx_rates": len(fx_rates),
            "transactions": len(transactions),
            "journals": len(journals),
            "ledger_entries": len(ledger_entries),
            "fee_assessments": len(fee_assessments),
            "fee_collections": len(fee_collections),
            "revenue_recognitions": len(revenue_recognitions),
        }
        total_records = sum(entity_counts.values())

        manifest = IngestionBatchManifest(
            batch_id=batch_id,
            generator_version="1.0.0",
            random_seed=self.config.seed,
            profile_name=self.config.profile,
            reporting_base_currency=self.config.reporting_base_currency,
            total_records=total_records,
            entity_counts=entity_counts,
            started_at=start_time,
            completed_at=completed_time,
            status="COMPLETED",
        )

        return GeneratedBatchData(
            manifest=manifest,
            gl_accounts=gl_accounts,
            customers=customers,
            accounts=accounts,
            overdraft_facilities=overdraft_facilities,
            fx_rates=fx_rates,
            transactions=transactions,
            journals=journals,
            ledger_entries=ledger_entries,
            fee_assessments=fee_assessments,
            fee_collections=fee_collections,
            revenue_recognitions=revenue_recognitions,
        )
