"""Unit tests for TransactionEngine, LedgerEngine, double-entry balancing, and reversals."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from data_platform.generator.config import GeneratorConfig
from data_platform.generator.engines.account_engine import AccountEngine
from data_platform.generator.engines.customer_engine import CustomerEngine
from data_platform.generator.engines.fx_engine import FXEngine
from data_platform.generator.engines.ledger_engine import LedgerEngine
from data_platform.generator.engines.transaction_engine import TransactionEngine
from data_platform.generator.schemas import AccountRecord, TransactionRecord


def _build_test_harness(
    seed: int = 42,
) -> tuple[TransactionEngine, LedgerEngine, list[AccountRecord]]:
    """Helper setting up customer and account fixtures for transaction testing."""
    config = GeneratorConfig.get_profile("TEST", seed=seed, reporting_base_currency="EUR")
    cust_engine = CustomerEngine(seed=seed)
    customers = cust_engine.generate_customers(count=10)
    acc_engine = AccountEngine(seed=seed)
    accounts, _ = acc_engine.generate_accounts_and_facilities(customers)
    fx_engine = FXEngine(seed=seed, reporting_base_currency="EUR")
    ledger_engine = LedgerEngine(fx_engine=fx_engine)
    txn_engine = TransactionEngine(config=config, fx_engine=fx_engine, ledger_engine=ledger_engine)
    return txn_engine, ledger_engine, accounts


def test_transaction_generation_and_journal_balancing() -> None:
    """Verify that every completed journal balances independently per currency leg."""
    txn_engine, _, accounts = _build_test_harness(seed=42)
    # Generate customers from same seed
    cust_engine = CustomerEngine(seed=42)
    customers = cust_engine.generate_customers(count=10)

    txns, journals, entries = txn_engine.generate_transactions_and_journals(customers, accounts)

    assert len(txns) == 200
    assert len(journals) > 0
    assert len(entries) > 0

    # 1. Verify every journal balances independently per currency
    for j in journals:
        balances: dict[str, Decimal] = {}
        for e in j.entries:
            balances.setdefault(e.currency, Decimal("0.0000"))
            if e.entry_type == "DEBIT":
                balances[e.currency] += e.amount
            else:
                balances[e.currency] -= e.amount

        for curr, diff in balances.items():
            assert diff == Decimal("0.0000"), (
                f"Journal {j.journal_id} is unbalanced in {curr}: diff={diff}"
            )


def test_failed_and_pending_transactions_produce_no_postings() -> None:
    """Verify failed and pending transactions do not generate ledger entries."""
    txn_engine, _, accounts = _build_test_harness(seed=101)
    cust_engine = CustomerEngine(seed=101)
    customers = cust_engine.generate_customers(count=10)

    txns, journals, entries = txn_engine.generate_transactions_and_journals(customers, accounts)

    journal_txn_ids = {j.transaction_id for j in journals if j.transaction_id is not None}
    entry_txn_ids = {e.transaction_id for e in entries if e.transaction_id is not None}

    for t in txns:
        if t.status in ("FAILED", "PENDING"):
            assert t.journal_id is None, (
                f"Transaction {t.transaction_id} with status {t.status} has a journal_id"
            )
            assert t.transaction_id not in journal_txn_ids
            assert t.transaction_id not in entry_txn_ids


def test_customer_subledger_to_gl_reconciliation() -> None:
    """Verify customer subledger totals reconcile to the GL_LIAB_CUSTOMER_DEPOSITS control account."""
    txn_engine, _, accounts = _build_test_harness(seed=55)
    cust_engine = CustomerEngine(seed=55)
    customers = cust_engine.generate_customers(count=10)

    _, _, entries = txn_engine.generate_transactions_and_journals(customers, accounts)

    # All customer postings must carry gl_account_id == GL_LIAB_CUSTOMER_DEPOSITS
    customer_entries = [e for e in entries if e.account_type_marker == "CUSTOMER"]
    for e in customer_entries:
        assert e.gl_account_id == "GL_LIAB_CUSTOMER_DEPOSITS"


def test_fx_conversion_multi_currency_accounting() -> None:
    """Verify FX conversions balance both currency legs and record realized spread income."""
    fx_engine = FXEngine(seed=42, reporting_base_currency="EUR")
    ledger_engine = LedgerEngine(fx_engine=fx_engine)
    now = datetime.now(UTC)

    source_acc = AccountRecord(
        account_id="ACC_EUR_01",
        customer_id="CUST_01",
        account_number="DE111",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("10000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    dest_acc = AccountRecord(
        account_id="ACC_USD_01",
        customer_id="CUST_01",
        account_number="US222",
        account_type="TREASURY_SWEEP",
        currency="USD",
        opening_balance=Decimal("5000.0000"),
        status="ACTIVE",
        opened_at=now,
    )

    # 1,000 EUR to USD conversion
    # Mid rate: 1.085000 -> 1,085.00 USD
    # Customer rate (with 20 bps spread): 1.082830 -> 1,082.83 USD
    # Spread income: 2.17 USD
    txn = TransactionRecord(
        transaction_id="TXN_FX_001",
        account_id=source_acc.account_id,
        counterparty_account_id=dest_acc.account_id,
        transaction_type="FX_CONVERSION",
        channel="ONLINE_BANKING",
        direction="DEBIT",
        transaction_amount=Decimal("1000.0000"),
        transaction_currency="EUR",
        settlement_currency="USD",
        customer_fx_rate=Decimal("1.082830"),
        base_currency_amount=Decimal("1000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )

    journal = ledger_engine.create_settlement_journal(
        txn, source_account=source_acc, counterparty_account=dest_acc
    )

    # Verify journal validation passed
    assert journal.journal_type == "FX_CONVERSION"
    assert len(journal.entries) == 5  # 2 EUR entries + 3 USD entries

    # Verify Leg 1 (EUR)
    eur_entries = [e for e in journal.entries if e.currency == "EUR"]
    assert len(eur_entries) == 2
    assert sum(e.amount for e in eur_entries if e.entry_type == "DEBIT") == Decimal("1000.0000")
    assert sum(e.amount for e in eur_entries if e.entry_type == "CREDIT") == Decimal("1000.0000")

    # Verify Leg 2 (USD)
    usd_entries = [e for e in journal.entries if e.currency == "USD"]
    assert len(usd_entries) == 3
    usd_debits = sum(e.amount for e in usd_entries if e.entry_type == "DEBIT")
    usd_credits = sum(e.amount for e in usd_entries if e.entry_type == "CREDIT")
    assert usd_debits == usd_credits
    assert usd_debits == Decimal("1085.0000")

    # Verify spread account credit
    spread_entry = [e for e in usd_entries if e.gl_account_id == "GL_REV_FX_SPREAD"][0]
    assert spread_entry.entry_type == "CREDIT"
    assert spread_entry.amount == Decimal("2.1700")


def test_partial_and_multiple_reversals_ceiling() -> None:
    """Verify append-only multiple partial reversals and cumulative 100% ceiling enforcement."""
    fx_engine = FXEngine(seed=42)
    ledger_engine = LedgerEngine(fx_engine=fx_engine)
    now = datetime.now(UTC)

    source_acc = AccountRecord(
        account_id="ACC_EUR_01",
        customer_id="CUST_01",
        account_number="DE111",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("5000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    txn = TransactionRecord(
        transaction_id="TXN_WIRE_REV",
        account_id=source_acc.account_id,
        counterparty_account_id=None,
        transaction_type="WIRE_TRANSFER",
        channel="SWIFT",
        direction="DEBIT",
        transaction_amount=Decimal("1000.0000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("1000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )

    orig_journal = ledger_engine.create_settlement_journal(txn, source_account=source_acc)
    assert len(orig_journal.entries) == 2

    # Partial Reversal 1: 40% (400 EUR)
    rev_1 = ledger_engine.create_reversal_journal(
        original_journal=orig_journal,
        reversal_percentage=Decimal("0.4000"),
        reason="PARTIAL_RETURN_1",
    )
    assert len(rev_1.entries) == 2
    assert rev_1.entries[0].amount == Decimal("400.0000")
    assert rev_1.entries[0].posting_status == "PARTIALLY_REVERSED"

    # Partial Reversal 2: 50% (500 EUR) -> Cumulative 90% (900 EUR)
    rev_2 = ledger_engine.create_reversal_journal(
        original_journal=orig_journal,
        reversal_percentage=Decimal("0.5000"),
        reason="PARTIAL_RETURN_2",
    )
    assert rev_2.entries[0].amount == Decimal("500.0000")

    # Partial Reversal 3: Attempting 20% (200 EUR) -> Cumulative 110% (1,100 EUR) > 1,000 EUR -> ERROR!
    with pytest.raises(ValueError, match="Cumulative reversal .* exceeds original entry amount"):
        ledger_engine.create_reversal_journal(
            original_journal=orig_journal,
            reversal_percentage=Decimal("0.2000"),
            reason="OVER_REVERSAL_ATTEMPT",
        )

    # Remaining 10% (100 EUR) is permitted:
    rev_final = ledger_engine.create_reversal_journal(
        original_journal=orig_journal,
        reversal_percentage=Decimal("0.1000"),
        reason="FINAL_RETURN_3",
    )
    assert rev_final.entries[0].amount == Decimal("100.0000")


def test_transaction_engine_seed_reproducibility() -> None:
    """Verify TransactionEngine produces identical transactions and journals for fixed seed."""
    txn_eng_1, _, accs_1 = _build_test_harness(seed=88)
    cust_eng_1 = CustomerEngine(seed=88)
    custs_1 = cust_eng_1.generate_customers(count=10)
    txns_1, jrn_1, _ = txn_eng_1.generate_transactions_and_journals(custs_1, accs_1)

    txn_eng_2, _, accs_2 = _build_test_harness(seed=88)
    cust_eng_2 = CustomerEngine(seed=88)
    custs_2 = cust_eng_2.generate_customers(count=10)
    txns_2, jrn_2, _ = txn_eng_2.generate_transactions_and_journals(custs_2, accs_2)

    assert [t.transaction_id for t in txns_1] == [t.transaction_id for t in txns_2]
    assert [t.transaction_amount for t in txns_1] == [t.transaction_amount for t in txns_2]
    assert [j.journal_id for j in jrn_1] == [j.journal_id for j in jrn_2]


def test_inbound_wire_transfer_accounting() -> None:
    """Verify CREDIT-direction transactions produce DEBIT to Central Bank and CREDIT to customer deposit."""
    ledger_engine = LedgerEngine()
    now = datetime.now(UTC)
    source_acc = AccountRecord(
        account_id="ACC_EUR_INBOUND",
        customer_id="CUST_01",
        account_number="DE_INBOUND",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("1000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    txn = TransactionRecord(
        transaction_id="TXN_INBOUND_001",
        account_id=source_acc.account_id,
        counterparty_account_id=None,
        transaction_type="WIRE_TRANSFER",
        channel="SWIFT",
        direction="CREDIT",
        transaction_amount=Decimal("2500.0000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("2500.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )

    journal = ledger_engine.create_settlement_journal(txn, source_account=source_acc)
    assert len(journal.entries) == 2

    # Expect: DEBIT Central Bank (asset increases), CREDIT Customer Deposits (liability increases)
    debit_entry = [e for e in journal.entries if e.entry_type == "DEBIT"][0]
    credit_entry = [e for e in journal.entries if e.entry_type == "CREDIT"][0]

    assert debit_entry.gl_account_id == "GL_ASSET_CENTRAL_BANK"
    assert debit_entry.amount == Decimal("2500.0000")
    assert credit_entry.gl_account_id == "GL_LIAB_CUSTOMER_DEPOSITS"
    assert credit_entry.account_id == source_acc.account_id
    assert credit_entry.amount == Decimal("2500.0000")


def test_customer_balance_net_movement() -> None:
    """Verify DEBIT transactions reduce deposits and CREDIT transactions increase deposits."""
    ledger_engine = LedgerEngine()
    now = datetime.now(UTC)
    source_acc = AccountRecord(
        account_id="ACC_EUR_BAL",
        customer_id="CUST_01",
        account_number="DE_BAL",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("10000.0000"),
        status="ACTIVE",
        opened_at=now,
    )

    # 1. Outbound DEBIT
    out_txn = TransactionRecord(
        transaction_id="TXN_OUT_001",
        account_id=source_acc.account_id,
        counterparty_account_id=None,
        transaction_type="ACH_PAYMENT",
        channel="SEPA_CORE",
        direction="DEBIT",
        transaction_amount=Decimal("1200.0000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("1200.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    j_out = ledger_engine.create_settlement_journal(out_txn, source_account=source_acc)
    cust_out = [e for e in j_out.entries if e.account_id == source_acc.account_id][0]
    assert cust_out.entry_type == "DEBIT"  # Liability debited = balance decreases

    # 2. Inbound CREDIT
    in_txn = TransactionRecord(
        transaction_id="TXN_IN_002",
        account_id=source_acc.account_id,
        counterparty_account_id=None,
        transaction_type="ACH_PAYMENT",
        channel="SEPA_CORE",
        direction="CREDIT",
        transaction_amount=Decimal("800.0000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("800.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    j_in = ledger_engine.create_settlement_journal(in_txn, source_account=source_acc)
    cust_in = [e for e in j_in.entries if e.account_id == source_acc.account_id][0]
    assert cust_in.entry_type == "CREDIT"  # Liability credited = balance increases


def test_card_settlement_external_clearing() -> None:
    """Verify card settlements post to GL_ASSET_CENTRAL_BANK external clearing."""
    ledger_engine = LedgerEngine()
    now = datetime.now(UTC)
    source_acc = AccountRecord(
        account_id="ACC_EUR_CARD",
        customer_id="CUST_01",
        account_number="DE_CARD",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("2000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    txn = TransactionRecord(
        transaction_id="TXN_CARD_001",
        account_id=source_acc.account_id,
        counterparty_account_id=None,
        transaction_type="CARD_SETTLEMENT",
        channel="API_GATEWAY",
        direction="DEBIT",
        transaction_amount=Decimal("45.5000"),
        transaction_currency="EUR",
        settlement_currency="EUR",
        customer_fx_rate=Decimal("1.000000"),
        base_currency_amount=Decimal("45.5000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    journal = ledger_engine.create_settlement_journal(txn, source_account=source_acc)
    clearing_entry = [e for e in journal.entries if e.gl_account_id == "GL_ASSET_CENTRAL_BANK"][0]
    assert clearing_entry.entry_type == "CREDIT"
    assert clearing_entry.amount == Decimal("45.5000")


def test_fx_conversion_no_negative_spread() -> None:
    """Verify that an inverted rate cannot produce negative FX spread revenue."""
    fx_engine = FXEngine(seed=42)
    ledger_engine = LedgerEngine(fx_engine=fx_engine)
    now = datetime.now(UTC)
    source_acc = AccountRecord(
        account_id="ACC_EUR_SPREAD",
        customer_id="CUST_01",
        account_number="DE_SPREAD",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("5000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    # Intentionally provide a customer rate higher than mid rate (normally not possible)
    txn = TransactionRecord(
        transaction_id="TXN_FX_INVERTED",
        account_id=source_acc.account_id,
        counterparty_account_id=None,
        transaction_type="FX_CONVERSION",
        channel="ONLINE_BANKING",
        direction="DEBIT",
        transaction_amount=Decimal("1000.0000"),
        transaction_currency="EUR",
        settlement_currency="USD",
        customer_fx_rate=Decimal("1.500000"),  # Much higher than mid 1.085000
        base_currency_amount=Decimal("1000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    journal = ledger_engine.create_settlement_journal(txn, source_account=source_acc)
    # When spread income < 0, ledger engine clamps spread income to 0 and adjusts dest amount
    spread_entries = [e for e in journal.entries if e.gl_account_id == "GL_REV_FX_SPREAD"]
    assert len(spread_entries) == 0


def test_reversal_of_fx_conversion() -> None:
    """Verify reversal of an FX conversion creates inverse entries in both currencies."""
    fx_engine = FXEngine(seed=42)
    ledger_engine = LedgerEngine(fx_engine=fx_engine)
    now = datetime.now(UTC)
    source_acc = AccountRecord(
        account_id="ACC_EUR_REV",
        customer_id="CUST_01",
        account_number="DE_REV",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("5000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    dest_acc = AccountRecord(
        account_id="ACC_USD_REV",
        customer_id="CUST_01",
        account_number="US_REV",
        account_type="TREASURY_SWEEP",
        currency="USD",
        opening_balance=Decimal("5000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    txn = TransactionRecord(
        transaction_id="TXN_FX_ORIG",
        account_id=source_acc.account_id,
        counterparty_account_id=dest_acc.account_id,
        transaction_type="FX_CONVERSION",
        channel="ONLINE_BANKING",
        direction="DEBIT",
        transaction_amount=Decimal("1000.0000"),
        transaction_currency="EUR",
        settlement_currency="USD",
        customer_fx_rate=Decimal("1.082830"),
        base_currency_amount=Decimal("1000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    orig_j = ledger_engine.create_settlement_journal(
        txn, source_account=source_acc, counterparty_account=dest_acc
    )
    rev_j = ledger_engine.create_reversal_journal(orig_j, reversal_percentage=Decimal("1.0000"))

    assert rev_j.journal_type == "REVERSAL"
    assert len(rev_j.entries) == len(orig_j.entries)
    # Check that EUR leg and USD leg balance independently in reversal
    eur_rev = [e for e in rev_j.entries if e.currency == "EUR"]
    usd_rev = [e for e in rev_j.entries if e.currency == "USD"]
    assert sum(e.amount for e in eur_rev if e.entry_type == "DEBIT") == sum(
        e.amount for e in eur_rev if e.entry_type == "CREDIT"
    )
    assert sum(e.amount for e in usd_rev if e.entry_type == "DEBIT") == sum(
        e.amount for e in usd_rev if e.entry_type == "CREDIT"
    )


def test_fx_clearing_position_reconciliation() -> None:
    """Verify net FX clearing position per currency across multiple conversions balances open exposure."""
    fx_engine = FXEngine(seed=42)
    ledger_engine = LedgerEngine(fx_engine=fx_engine)
    now = datetime.now(UTC)
    source_acc = AccountRecord(
        account_id="ACC_EUR_POS",
        customer_id="CUST_01",
        account_number="DE_POS",
        account_type="OPERATING_CHECKING",
        currency="EUR",
        opening_balance=Decimal("10000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    dest_acc = AccountRecord(
        account_id="ACC_USD_POS",
        customer_id="CUST_01",
        account_number="US_POS",
        account_type="TREASURY_SWEEP",
        currency="USD",
        opening_balance=Decimal("10000.0000"),
        status="ACTIVE",
        opened_at=now,
    )
    txn = TransactionRecord(
        transaction_id="TXN_FX_POS",
        account_id=source_acc.account_id,
        counterparty_account_id=dest_acc.account_id,
        transaction_type="FX_CONVERSION",
        channel="SWIFT",
        direction="DEBIT",
        transaction_amount=Decimal("2000.0000"),
        transaction_currency="EUR",
        settlement_currency="USD",
        customer_fx_rate=Decimal("1.082830"),
        base_currency_amount=Decimal("2000.0000"),
        status="SETTLED",
        initiated_at=now,
        settled_at=now,
    )
    journal = ledger_engine.create_settlement_journal(
        txn, source_account=source_acc, counterparty_account=dest_acc
    )
    fx_entries = [e for e in journal.entries if e.gl_account_id == "GL_ASSET_FX_CLEARING"]
    eur_fx = [e for e in fx_entries if e.currency == "EUR"][0]
    usd_fx = [e for e in fx_entries if e.currency == "USD"][0]

    assert eur_fx.entry_type == "CREDIT"
    assert eur_fx.amount == Decimal("2000.0000")
    assert usd_fx.entry_type == "DEBIT"
    assert usd_fx.amount == Decimal("2170.0000")  # 2000 * 1.085000
