"""Unit tests validating financial schemas, constraints, and accounting rules."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from data_platform.generator.config import STANDARD_GL_ACCOUNTS, GeneratorConfig
from data_platform.generator.schemas import (
    AccountRecord,
    CustomerRecord,
    FeeAssessmentRecord,
    FeeCollectionRecord,
    FXRateRecord,
    GLAccountRecord,
    IngestionBatchManifest,
    LedgerEntryRecord,
    OverdraftFacilityRecord,
    RevenueRecognitionRecord,
    TransactionRecord,
)


def test_gl_accounts_master_definitions() -> None:
    """Verify standard GL accounts master catalog is valid."""
    assert len(STANDARD_GL_ACCOUNTS) >= 10
    account_ids = {a.gl_account_id for a in STANDARD_GL_ACCOUNTS}
    assert "GL_ASSET_CENTRAL_BANK" in account_ids
    assert "GL_LIAB_CUSTOMER_DEPOSITS" in account_ids
    assert "GL_REV_WIRE_FEES" in account_ids
    assert "GL_ASSET_FX_CLEARING" in account_ids


def test_gl_account_schema_validation() -> None:
    """Verify GL account record validation."""
    gl = GLAccountRecord(
        gl_account_id="GL_ASSET_CASH",
        gl_account_number="1010",
        account_name="Cash on Hand",
        account_category="ASSET",
        normal_balance="DEBIT",
        currency="EUR",
        description="Cash reserve",
    )
    assert gl.normal_balance == "DEBIT"
    assert gl.currency == "EUR"


def test_customer_and_account_schemas() -> None:
    """Verify customer profile and account models."""
    now = datetime.now(UTC)
    cust = CustomerRecord(
        customer_id="CUST_1001",
        legal_entity_id="ENTITY_US",
        customer_name="Acme Treasury Corp",
        customer_segment="COMMERCIAL_SME",
        status="ACTIVE",
        onboarding_date=date(2025, 1, 15),
    )
    assert cust.customer_segment == "COMMERCIAL_SME"

    acc = AccountRecord(
        account_id="ACC_2001",
        customer_id=cust.customer_id,
        account_number="DE89370400440532013000",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("150000.0000"),
        reserved_funds=Decimal("5000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    assert acc.opening_balance == Decimal("150000.0000")
    assert acc.reserved_funds == Decimal("5000.0000")


def test_transaction_and_ledger_entry_schemas() -> None:
    """Verify commercial transaction and balanced double-entry ledger postings."""
    now = datetime.now(UTC)
    txn = TransactionRecord(
        transaction_id="TXN_9001",
        account_id="ACC_2001",
        counterparty_account_id="ACC_3001",
        transaction_type="WIRE_TRANSFER",
        channel="SWIFT",
        direction="DEBIT",
        transaction_amount=Decimal("10000.0000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("10000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    assert txn.transaction_amount == Decimal("10000.0000")

    # Balanced ledger pair for this transaction:
    # 1. Customer liability decreased (DEBIT)
    # 2. Central bank cash decreased (CREDIT)
    debit_entry = LedgerEntryRecord(
        entry_id="LE_001_DR",
        journal_id="JRN_001",
        transaction_id=txn.transaction_id,
        account_id=txn.account_id,
        account_type_marker="CUSTOMER",
        gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
        entry_type="DEBIT",
        amount=txn.transaction_amount,
        currency="EUR",
        posting_status="POSTED",
        posted_at=now,
    )
    credit_entry = LedgerEntryRecord(
        entry_id="LE_001_CR",
        journal_id="JRN_001",
        transaction_id=txn.transaction_id,
        account_id="GL_ASSET_CENTRAL_BANK",
        account_type_marker="GL_INTERNAL",
        gl_account_id="GL_ASSET_CENTRAL_BANK",
        entry_type="CREDIT",
        amount=txn.transaction_amount,
        currency="EUR",
        posting_status="POSTED",
        posted_at=now,
    )
    assert debit_entry.amount == credit_entry.amount
    assert debit_entry.currency == credit_entry.currency

    from data_platform.generator.schemas import JournalRecord

    journal = JournalRecord(
        journal_id="JRN_001",
        transaction_id=txn.transaction_id,
        journal_type="WIRE_SETTLEMENT",
        description="Wire settlement",
        created_at=now,
        entries=[debit_entry, credit_entry],
    )
    assert len(journal.entries) == 2


def test_generator_config_profiles() -> None:
    """Verify preset generator configurations and default EUR currency."""
    dev_cfg = GeneratorConfig.get_profile("DEV")
    assert dev_cfg.reporting_base_currency == "EUR"
    assert dev_cfg.customer_count == 50
    assert dev_cfg.transaction_count == 5000

    test_cfg = GeneratorConfig.get_profile("TEST", seed=99, reporting_base_currency="USD")
    assert test_cfg.seed == 99
    assert test_cfg.reporting_base_currency == "USD"
    assert test_cfg.transaction_count == 200


def test_fx_rate_validation() -> None:
    """Verify FX rate spread constraints (bid <= mid <= ask)."""
    now = datetime.now(UTC)
    rate = FXRateRecord(
        rate_id="FX_EUR_USD_20250101",
        rate_date=date(2025, 1, 1),
        from_currency="EUR",
        to_currency="USD",
        mid_rate=Decimal("1.085000"),
        bid_rate=Decimal("1.084500"),
        ask_rate=Decimal("1.085500"),
        rate_source="ECB_SYNTH",
        rate_type="HISTORICAL_EOD",
        rate_timestamp=now,
    )
    assert rate.mid_rate == Decimal("1.085000")

    # Invalid spread: Bid exceeds Mid
    with pytest.raises(ValueError, match="Bid rate .* cannot exceed mid rate"):
        FXRateRecord(
            rate_id="FX_INVALID",
            rate_date=date(2025, 1, 1),
            from_currency="EUR",
            to_currency="USD",
            mid_rate=Decimal("1.085000"),
            bid_rate=Decimal("1.086000"),
            ask_rate=Decimal("1.087000"),
            rate_source="ECB_SYNTH",
            rate_type="SPOT",
            rate_timestamp=now,
        )


def test_overdraft_facility_dates() -> None:
    """Verify effective dates on overdraft agreements."""
    with pytest.raises(ValueError, match="effective_end_date cannot be earlier"):
        OverdraftFacilityRecord(
            facility_id="OD_1",
            account_id="ACC_1",
            authorized_limit=Decimal("5000.0000"),
            standard_interest_rate=Decimal("0.0850"),
            unauthorized_penalty_rate=Decimal("0.1800"),
            effective_start_date=date(2025, 6, 1),
            effective_end_date=date(2025, 5, 1),
        )


def test_fee_assessment_decomposition_math() -> None:
    """Verify gross_assessed == waived + collectible."""
    now = datetime.now(UTC)
    assessment = FeeAssessmentRecord(
        assessment_id="FA_1",
        transaction_id="TX_1",
        account_id="ACC_1",
        gross_assessed_amount=Decimal("35.0000"),
        waived_amount=Decimal("10.0000"),
        waiver_reason="COMMERCIAL_TIER_DISCOUNT",
        net_collectible_amount=Decimal("25.0000"),
        assessment_status="PARTIALLY_WAIVED",
        assessed_at=now,
    )
    assert assessment.net_collectible_amount == Decimal("25.0000")

    with pytest.raises(ValueError, match="must exactly equal waived amount"):
        FeeAssessmentRecord(
            assessment_id="FA_INVALID",
            transaction_id="TX_1",
            account_id="ACC_1",
            gross_assessed_amount=Decimal("35.0000"),
            waived_amount=Decimal("10.0000"),
            net_collectible_amount=Decimal("30.0000"),
            assessment_status="PARTIALLY_WAIVED",
            assessed_at=now,
        )


def test_fee_collection_lifecycle_math() -> None:
    """Verify target == collected + outstanding."""
    now = datetime.now(UTC)
    partial = FeeCollectionRecord(
        collection_id="FC_1",
        assessment_id="FA_1",
        account_id="ACC_1",
        collection_attempt_number=1,
        target_amount=Decimal("25.0000"),
        collected_amount=Decimal("15.0000"),
        outstanding_amount=Decimal("10.0000"),
        collection_status="PARTIAL",
        failure_reason="INSUFFICIENT_AVAILABLE_FUNDS",
        attempted_at=now,
        settled_at=now,
        linked_ledger_entry_id="LE_FEE_1",
    )
    assert partial.collected_amount == Decimal("15.0000")
    assert partial.outstanding_amount == Decimal("10.0000")

    with pytest.raises(ValueError, match="SETTLED collection cannot have positive outstanding"):
        FeeCollectionRecord(
            collection_id="FC_INVALID",
            assessment_id="FA_1",
            account_id="ACC_1",
            target_amount=Decimal("25.0000"),
            collected_amount=Decimal("20.0000"),
            outstanding_amount=Decimal("5.0000"),
            collection_status="SETTLED",
            attempted_at=now,
        )


def test_revenue_recognition_net_calculation() -> None:
    """Verify net revenue = gross - reversals - network costs."""
    now = datetime.now(UTC)
    rev = RevenueRecognitionRecord(
        recognition_id="RR_1",
        collection_id="FC_1",
        gross_collected_revenue=Decimal("100.0000"),
        reversed_revenue_amount=Decimal("15.0000"),
        pass_through_cost=Decimal("5.0000"),
        net_recognized_revenue=Decimal("80.0000"),
        recognized_at=now,
    )
    assert rev.net_recognized_revenue == Decimal("80.0000")

    with pytest.raises(ValueError, match="Net recognized revenue .* must equal"):
        RevenueRecognitionRecord(
            recognition_id="RR_INVALID",
            collection_id="FC_1",
            gross_collected_revenue=Decimal("100.0000"),
            reversed_revenue_amount=Decimal("15.0000"),
            pass_through_cost=Decimal("5.0000"),
            net_recognized_revenue=Decimal("95.0000"),
            recognized_at=now,
        )


def test_batch_manifest_schema() -> None:
    """Verify batch manifest creation."""
    now = datetime.now(UTC)
    manifest = IngestionBatchManifest(
        batch_id=uuid4(),
        generator_version="1.0.0",
        random_seed=42,
        profile_name="DEV",
        reporting_base_currency="EUR",
        total_records=5000,
        entity_counts={"customers": 50, "transactions": 5000},
        started_at=now,
        completed_at=now,
        status="COMPLETED",
    )
    assert manifest.reporting_base_currency == "EUR"
    assert manifest.random_seed == 42
