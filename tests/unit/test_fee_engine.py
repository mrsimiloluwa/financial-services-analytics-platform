"""Unit tests for FeeEngine, pricing rules, contractual overrides, collection lifecycles, and journal integration."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from data_platform.generator.engines.fee_engine import FeeEngine, PricingRule
from data_platform.generator.schemas import AccountRecord, TransactionRecord


@pytest.fixture
def test_accounts() -> tuple[AccountRecord, AccountRecord]:
    now = datetime.now(UTC)
    active_acc = AccountRecord(
        account_id="ACC_FEE_EUR_01",
        customer_id="CUST_CORP_01",
        account_number="DE_CORP_01",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("50000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    frozen_acc = AccountRecord(
        account_id="ACC_FEE_EUR_FROZEN",
        customer_id="CUST_CORP_02",
        account_number="DE_FROZEN_01",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("10000.0000"),
        status="FROZEN",
        opened_at=now,
    )
    return active_acc, frozen_acc


def test_standard_pricing_catalogue_segment_resolution() -> None:
    """Verify segment-specific rule resolution for Institutional, Commercial, and Retail."""
    engine = FeeEngine()
    test_date = date(2025, 6, 1)

    # 1. Institutional wire: 15 EUR base + 5 bps
    inst_rule = engine.resolve_pricing_rule("WIRE_TRANSFER", "INSTITUTIONAL", test_date)
    assert inst_rule is not None
    assert inst_rule.base_fee == Decimal("15.0000")
    assert inst_rule.basis_points == Decimal("0.0005")

    # 2. Commercial SME wire: 10 EUR base + 10 bps
    sme_rule = engine.resolve_pricing_rule("WIRE_TRANSFER", "COMMERCIAL_SME", test_date)
    assert sme_rule is not None
    assert sme_rule.base_fee == Decimal("10.0000")
    assert sme_rule.basis_points == Decimal("0.0010")

    # 3. Retail wire: 5 EUR base + 15 bps
    retail_rule = engine.resolve_pricing_rule("WIRE_TRANSFER", "RETAIL_WEALTH", test_date)
    assert retail_rule is not None
    assert retail_rule.base_fee == Decimal("5.0000")
    assert retail_rule.basis_points == Decimal("0.0015")


def test_contractual_pricing_override_precedence() -> None:
    """Verify active contractual overrides take priority over standard catalogue."""
    override = PricingRule(
        rule_id="OVR_VIP_WIRE",
        transaction_type="WIRE_TRANSFER",
        customer_segment="COMMERCIAL_SME",
        base_fee=Decimal("2.0000"),  # Highly discounted VIP rate
        basis_points=Decimal("0.0001"),  # 1 bp
        currency="EUR",
        effective_start=date(2025, 1, 1),
        effective_end=date(2025, 6, 30),
        description="VIP negotiated rate H1 2025",
        is_override=True,
    )
    engine = FeeEngine(overrides=[override])

    # Date within override window
    rule_in_window = engine.resolve_pricing_rule(
        "WIRE_TRANSFER", "COMMERCIAL_SME", date(2025, 3, 15)
    )
    assert rule_in_window is not None
    assert rule_in_window.rule_id == "OVR_VIP_WIRE"
    assert rule_in_window.base_fee == Decimal("2.0000")

    # Date outside override window falls back to standard catalogue
    rule_post_window = engine.resolve_pricing_rule(
        "WIRE_TRANSFER", "COMMERCIAL_SME", date(2025, 8, 1)
    )
    assert rule_post_window is not None
    assert rule_post_window.rule_id == "RULE_WIRE_COMMERCIAL"
    assert rule_post_window.base_fee == Decimal("10.0000")


def test_fee_assessment_calculation_and_waivers(
    test_accounts: tuple[AccountRecord, AccountRecord],
) -> None:
    """Verify gross calculation, percentage waiver application, and net collectible derivation."""
    active_acc, _ = test_accounts
    engine = FeeEngine()
    now = datetime(2025, 5, 1, 10, 0, tzinfo=UTC)

    # 100,000 EUR Institutional Wire:
    # Base fee: 15.0000 EUR
    # Variable fee (5 bps): 100,000 * 0.0005 = 50.0000 EUR
    # Gross assessed: 65.0000 EUR
    txn = TransactionRecord(
        transaction_id="TXN_ASSESS_01",
        account_id=active_acc.account_id,
        transaction_type="WIRE_TRANSFER",
        channel="SWIFT",
        direction="DEBIT",
        transaction_amount=Decimal("100000.0000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("100000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )

    # 1. No waiver
    assessment_full = engine.assess_fee(txn, customer_segment="INSTITUTIONAL")
    assert assessment_full is not None
    assert assessment_full.gross_assessed_amount == Decimal("65.0000")
    assert assessment_full.waived_amount == Decimal("0.0000")
    assert assessment_full.net_collectible_amount == Decimal("65.0000")
    assert assessment_full.assessment_status == "ASSESSED"

    # 2. 20% promotional waiver
    assessment_partial = engine.assess_fee(
        txn,
        customer_segment="INSTITUTIONAL",
        waiver_percentage=Decimal("0.2000"),
        waiver_reason="VOLUME_PROMO_2025",
    )
    assert assessment_partial is not None
    assert assessment_partial.gross_assessed_amount == Decimal("65.0000")
    assert assessment_partial.waived_amount == Decimal("13.0000")
    assert assessment_partial.net_collectible_amount == Decimal("52.0000")
    assert assessment_partial.assessment_status == "PARTIALLY_WAIVED"

    # 3. 100% full waiver
    assessment_full_waiver = engine.assess_fee(
        txn,
        customer_segment="INSTITUTIONAL",
        waiver_percentage=Decimal("1.0000"),
        waiver_reason="COURTESY_WAIVER",
    )
    assert assessment_full_waiver is not None
    assert assessment_full_waiver.gross_assessed_amount == Decimal("65.0000")
    assert assessment_full_waiver.waived_amount == Decimal("65.0000")
    assert assessment_full_waiver.net_collectible_amount == Decimal("0.0000")
    assert assessment_full_waiver.assessment_status == "WAIVED_IN_FULL"


def test_failed_collection_creates_no_journal(
    test_accounts: tuple[AccountRecord, AccountRecord],
) -> None:
    """Verify failed collection attempts on frozen accounts produce no accounting journal postings."""
    active_acc, frozen_acc = test_accounts
    engine = FeeEngine()
    now = datetime(2025, 5, 1, 10, 0, tzinfo=UTC)

    txn = TransactionRecord(
        transaction_id="TXN_FAIL_01",
        account_id=frozen_acc.account_id,
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
    assessment = engine.assess_fee(txn, customer_segment="COMMERCIAL_SME")
    assert assessment is not None

    record, journal, recognition = engine.execute_collection_attempt(
        assessment=assessment,
        account=frozen_acc,
        attempt_number=1,
    )

    assert record.collection_status == "FAILED"
    assert record.failure_reason == "ACCOUNT_FROZEN"
    assert record.collected_amount == Decimal("0.0000")
    assert record.linked_ledger_entry_id is None
    assert journal is None
    assert recognition is None


def test_multi_attempt_settlement_and_double_entry_postings(
    test_accounts: tuple[AccountRecord, AccountRecord],
) -> None:
    """Verify multi-attempt sweep, double-entry balancing, and ledger entry linking."""
    active_acc, _ = test_accounts
    engine = FeeEngine()
    now = datetime(2025, 5, 1, 10, 0, tzinfo=UTC)

    txn = TransactionRecord(
        transaction_id="TXN_MULTI_01",
        account_id=active_acc.account_id,
        transaction_type="WIRE_TRANSFER",
        channel="SWIFT",
        direction="DEBIT",
        transaction_amount=Decimal("50000.0000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("50000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    # Assessed: base 10 + (50,000 * 0.0010) = 60 EUR net collectible
    assessment = engine.assess_fee(txn, customer_segment="COMMERCIAL_SME")
    assert assessment is not None
    assert assessment.net_collectible_amount == Decimal("60.0000")

    # Attempt 1: Partial collection of 40 EUR
    rec_1, j_1, rev_1 = engine.execute_collection_attempt(
        assessment=assessment,
        account=active_acc,
        attempt_number=1,
        collected_amount=Decimal("40.0000"),
        pass_through_cost=Decimal("2.5000"),
    )
    assert rec_1.collection_status == "PARTIAL"
    assert rec_1.target_amount == Decimal("60.0000")
    assert rec_1.collected_amount == Decimal("40.0000")
    assert rec_1.outstanding_amount == Decimal("20.0000")
    assert rec_1.linked_ledger_entry_id is not None
    assert j_1 is not None
    assert rev_1 is not None
    assert rev_1.net_recognized_revenue == Decimal("37.5000")  # 40 - 2.50

    # Verify Journal 1 is balanced
    assert j_1.journal_type == "FEE_SETTLEMENT"
    assert len(j_1.entries) == 2
    debit_entry = [e for e in j_1.entries if e.entry_type == "DEBIT"][0]
    credit_entry = [e for e in j_1.entries if e.entry_type == "CREDIT"][0]
    assert debit_entry.gl_account_id == "GL_LIAB_CUSTOMER_DEPOSITS"
    assert debit_entry.amount == Decimal("40.0000")
    assert credit_entry.gl_account_id == "GL_REV_WIRE_FEES"
    assert credit_entry.amount == Decimal("40.0000")

    # Attempt 2: Remaining 20 EUR sweep
    rec_2, j_2, rev_2 = engine.execute_collection_attempt(
        assessment=assessment,
        account=active_acc,
        attempt_number=2,
    )
    assert rec_2.collection_status == "SETTLED"
    assert rec_2.collected_amount == Decimal("20.0000")
    assert j_2 is not None
    assert rev_2 is not None

    # Total collected equals collectible ceiling
    assert rec_1.collected_amount + rec_2.collected_amount == assessment.net_collectible_amount
    # Ledger IDs across retries are strictly distinct
    assert rec_1.linked_ledger_entry_id != rec_2.linked_ledger_entry_id

    # Attempt 3: Further attempt rejected because assessment is fully settled
    with pytest.raises(ValueError, match="already fully collected"):
        engine.execute_collection_attempt(
            assessment=assessment, account=active_acc, attempt_number=3
        )
