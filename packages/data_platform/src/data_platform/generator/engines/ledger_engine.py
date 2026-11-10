"""Double-entry ledger engine constructing balanced multi-currency accounting journals."""

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

from data_platform.generator.engines.fx_engine import FXEngine
from data_platform.generator.schemas import (
    AccountRecord,
    JournalRecord,
    LedgerEntryRecord,
    TransactionRecord,
)


class LedgerEngine:
    """Constructs balanced double-entry accounting journals and enforces ledger invariants."""

    def __init__(self, fx_engine: FXEngine | None = None) -> None:
        self.fx_engine = fx_engine or FXEngine()
        self.entry_counter = 1
        self.journal_counter = 1
        # Track cumulative reversals per original ledger entry: original_entry_id -> Decimal
        self.cumulative_reversals: dict[str, Decimal] = {}

    def _next_journal_id(self) -> str:
        jid = f"JRN_{self.journal_counter:07d}"
        self.journal_counter += 1
        return jid

    def _next_entry_id(self) -> str:
        eid = f"LE_{self.entry_counter:08d}"
        self.entry_counter += 1
        return eid

    def create_settlement_journal(
        self,
        transaction: TransactionRecord,
        source_account: AccountRecord,
        counterparty_account: AccountRecord | None = None,
    ) -> JournalRecord:
        """Create a balanced journal for a settled transaction.

        For single-currency transactions, debits and credits balance in the transaction currency.
        For FX conversions, two independent balanced currency legs are created via FX Clearing.
        """
        if transaction.status not in ("SETTLED", "REVERSED"):
            raise ValueError(
                f"Cannot generate ledger entries for non-settled transaction (status: {transaction.status})"
            )

        journal_id = self._next_journal_id()
        posting_time = transaction.settled_at or transaction.initiated_at
        entries: list[LedgerEntryRecord] = []

        if transaction.transaction_type == "FX_CONVERSION":
            # Multi-Currency FX Conversion
            entries.extend(
                self._build_fx_conversion_legs(
                    journal_id=journal_id,
                    transaction=transaction,
                    source_account=source_account,
                    dest_account=counterparty_account,
                    posting_time=posting_time,
                )
            )
            journal_type = "FX_CONVERSION"
            desc = f"FX Conversion: {transaction.transaction_amount} {transaction.transaction_currency} -> {transaction.settlement_currency}"
        else:
            # Single-Currency Payments (Wire, ACH, Card Settlement)
            # Note: Card settlements clear through GL_ASSET_CENTRAL_BANK as an architectural simplification
            # for external clearing rails, rather than introducing dedicated scheme clearing subledgers.
            entries.extend(
                self._build_single_currency_legs(
                    journal_id=journal_id,
                    transaction=transaction,
                    source_account=source_account,
                    counterparty_account=counterparty_account,
                    posting_time=posting_time,
                )
            )
            journal_type = (
                "WIRE_SETTLEMENT"
                if transaction.transaction_type == "WIRE_TRANSFER"
                else (
                    "ACH_SETTLEMENT"
                    if transaction.transaction_type == "ACH_PAYMENT"
                    else "CARD_SETTLEMENT"
                )
            )
            desc = f"{transaction.transaction_type} settlement ({transaction.channel})"

        journal = JournalRecord(
            journal_id=journal_id,
            transaction_id=transaction.transaction_id,
            journal_type=journal_type,
            description=desc,
            created_at=posting_time,
            entries=entries,
        )
        return journal

    def _build_single_currency_legs(
        self,
        journal_id: str,
        transaction: TransactionRecord,
        source_account: AccountRecord,
        counterparty_account: AccountRecord | None,
        posting_time: datetime,
    ) -> list[LedgerEntryRecord]:
        """Build balanced debits and credits for standard single-currency transactions."""
        curr = transaction.transaction_currency
        amt = transaction.transaction_amount
        entries: list[LedgerEntryRecord] = []

        if transaction.direction == "DEBIT":
            # 1. Customer deposit account is debited (liability decreases)
            entries.append(
                LedgerEntryRecord(
                    entry_id=self._next_entry_id(),
                    journal_id=journal_id,
                    transaction_id=transaction.transaction_id,
                    account_id=source_account.account_id,
                    account_type_marker="CUSTOMER",
                    gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
                    entry_type="DEBIT",
                    amount=amt,
                    currency=curr,
                    posted_at=posting_time,
                )
            )
            # 2. If internal counterparty exists, credit counterparty deposit account;
            # otherwise credit external clearing settlement (asset decreases)
            credit_acc_id = (
                counterparty_account.account_id if counterparty_account else "GL_ASSET_CENTRAL_BANK"
            )
            credit_marker = "CUSTOMER" if counterparty_account else "GL_INTERNAL"
            credit_gl = (
                "GL_LIAB_CUSTOMER_DEPOSITS" if counterparty_account else "GL_ASSET_CENTRAL_BANK"
            )

            entries.append(
                LedgerEntryRecord(
                    entry_id=self._next_entry_id(),
                    journal_id=journal_id,
                    transaction_id=transaction.transaction_id,
                    account_id=credit_acc_id,
                    account_type_marker=credit_marker,
                    gl_account_id=credit_gl,
                    entry_type="CREDIT",
                    amount=amt,
                    currency=curr,
                    posted_at=posting_time,
                )
            )
        else:
            # Direction == "CREDIT" (Inbound money)
            debit_acc_id = (
                counterparty_account.account_id if counterparty_account else "GL_ASSET_CENTRAL_BANK"
            )
            debit_marker = "CUSTOMER" if counterparty_account else "GL_INTERNAL"
            debit_gl = (
                "GL_LIAB_CUSTOMER_DEPOSITS" if counterparty_account else "GL_ASSET_CENTRAL_BANK"
            )

            entries.append(
                LedgerEntryRecord(
                    entry_id=self._next_entry_id(),
                    journal_id=journal_id,
                    transaction_id=transaction.transaction_id,
                    account_id=debit_acc_id,
                    account_type_marker=debit_marker,
                    gl_account_id=debit_gl,
                    entry_type="DEBIT",
                    amount=amt,
                    currency=curr,
                    posted_at=posting_time,
                )
            )
            entries.append(
                LedgerEntryRecord(
                    entry_id=self._next_entry_id(),
                    journal_id=journal_id,
                    transaction_id=transaction.transaction_id,
                    account_id=source_account.account_id,
                    account_type_marker="CUSTOMER",
                    gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
                    entry_type="CREDIT",
                    amount=amt,
                    currency=curr,
                    posted_at=posting_time,
                )
            )

        return entries

    def _build_fx_conversion_legs(
        self,
        journal_id: str,
        transaction: TransactionRecord,
        source_account: AccountRecord,
        dest_account: AccountRecord | None,
        posting_time: datetime,
    ) -> list[LedgerEntryRecord]:
        """Build two independently balanced currency legs for FX conversions.

        Note on FX Clearing Account (GL_ASSET_FX_CLEARING):
        GL_ASSET_FX_CLEARING serves as an open position / suspense clearing account bridging
        the two currency legs. Across conversions, it accumulates per-currency debit or credit balances
        reflecting the bank's net open currency positions, while each transaction journal balances
        strictly per-currency:
          - Leg 1 (Sell/Source): DEBIT Customer Deposits, CREDIT FX Clearing in source currency.
          - Leg 2 (Buy/Dest): DEBIT FX Clearing, CREDIT Customer Deposits + FX Spread Revenue in dest currency.
        """
        from_curr = transaction.transaction_currency
        to_curr = transaction.settlement_currency
        from_amount = transaction.transaction_amount

        # Mid-market rate and customer realized rate
        rate_date = posting_time.date()
        mid_rate = self.fx_engine.get_mid_rate(from_curr, to_curr, rate_date)
        cust_rate = transaction.customer_fx_rate

        # Destination amounts in to_curr
        mid_dest_amount = (from_amount * mid_rate).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        )
        cust_dest_amount = (from_amount * cust_rate).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        )
        fx_spread_income = (mid_dest_amount - cust_dest_amount).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_EVEN,
        )
        if fx_spread_income < Decimal("0.0000"):
            # Ensure bank does not record negative spread on normal retail FX
            fx_spread_income = Decimal("0.0000")
            cust_dest_amount = mid_dest_amount

        entries: list[LedgerEntryRecord] = []

        # =====================================================================
        # Leg 1: Source Currency (from_curr)
        # Debit Customer Deposit Account, Credit Bank FX Clearing Account
        # =====================================================================
        entries.append(
            LedgerEntryRecord(
                entry_id=self._next_entry_id(),
                journal_id=journal_id,
                transaction_id=transaction.transaction_id,
                account_id=source_account.account_id,
                account_type_marker="CUSTOMER",
                gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
                entry_type="DEBIT",
                amount=from_amount,
                currency=from_curr,
                posted_at=posting_time,
            )
        )
        entries.append(
            LedgerEntryRecord(
                entry_id=self._next_entry_id(),
                journal_id=journal_id,
                transaction_id=transaction.transaction_id,
                account_id="GL_ASSET_FX_CLEARING",
                account_type_marker="GL_INTERNAL",
                gl_account_id="GL_ASSET_FX_CLEARING",
                entry_type="CREDIT",
                amount=from_amount,
                currency=from_curr,
                posted_at=posting_time,
            )
        )

        # =====================================================================
        # Leg 2: Destination Currency (to_curr)
        # Debit Bank FX Clearing Account for mid_dest_amount
        # Credit Customer Deposit Account for cust_dest_amount
        # Credit Bank FX Spread Revenue Account for fx_spread_income
        # Balance in to_curr: mid_dest_amount == cust_dest_amount + fx_spread_income
        # =====================================================================
        target_account_id = dest_account.account_id if dest_account else source_account.account_id

        entries.append(
            LedgerEntryRecord(
                entry_id=self._next_entry_id(),
                journal_id=journal_id,
                transaction_id=transaction.transaction_id,
                account_id="GL_ASSET_FX_CLEARING",
                account_type_marker="GL_INTERNAL",
                gl_account_id="GL_ASSET_FX_CLEARING",
                entry_type="DEBIT",
                amount=mid_dest_amount,
                currency=to_curr,
                posted_at=posting_time,
            )
        )
        entries.append(
            LedgerEntryRecord(
                entry_id=self._next_entry_id(),
                journal_id=journal_id,
                transaction_id=transaction.transaction_id,
                account_id=target_account_id,
                account_type_marker="CUSTOMER",
                gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
                entry_type="CREDIT",
                amount=cust_dest_amount,
                currency=to_curr,
                posted_at=posting_time,
            )
        )
        if fx_spread_income > Decimal("0.0000"):
            entries.append(
                LedgerEntryRecord(
                    entry_id=self._next_entry_id(),
                    journal_id=journal_id,
                    transaction_id=transaction.transaction_id,
                    account_id="GL_REV_FX_SPREAD",
                    account_type_marker="GL_INTERNAL",
                    gl_account_id="GL_REV_FX_SPREAD",
                    entry_type="CREDIT",
                    amount=fx_spread_income,
                    currency=to_curr,
                    posted_at=posting_time,
                )
            )

        return entries

    def create_reversal_journal(
        self,
        original_journal: JournalRecord,
        reversal_percentage: Decimal = Decimal("1.0000"),
        reversal_timestamp: datetime | None = None,
        reason: str = "COMMERCIAL_DISPUTE_REVERSAL",
    ) -> JournalRecord:
        """Create an append-only reversal journal supporting full or partial reversals.

        Enforces that cumulative reversals for any original entry never exceed 100%.
        Inverses DEBIT to CREDIT and CREDIT to DEBIT, preserving independent currency balancing.
        """
        if not (Decimal("0.0000") < reversal_percentage <= Decimal("1.0000")):
            raise ValueError(
                f"Reversal percentage must be between 0.0001 and 1.0000 (got {reversal_percentage})"
            )

        rev_journal_id = self._next_journal_id()
        rev_time = reversal_timestamp or original_journal.created_at
        rev_entries: list[LedgerEntryRecord] = []

        for orig in original_journal.entries:
            reversal_amount = (orig.amount * reversal_percentage).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_EVEN,
            )
            # Cumulative ceiling check
            current_rev_total = self.cumulative_reversals.get(orig.entry_id, Decimal("0.0000"))
            if (current_rev_total + reversal_amount) > orig.amount:
                raise ValueError(
                    f"Cumulative reversal ({current_rev_total + reversal_amount}) exceeds "
                    f"original entry amount ({orig.amount}) for entry {orig.entry_id}"
                )
            self.cumulative_reversals[orig.entry_id] = current_rev_total + reversal_amount

            # Inverse debit/credit entry
            inverse_type = "CREDIT" if orig.entry_type == "DEBIT" else "DEBIT"
            status = (
                "REVERSED" if reversal_percentage == Decimal("1.0000") else "PARTIALLY_REVERSED"
            )

            rev_entry = LedgerEntryRecord(
                entry_id=self._next_entry_id(),
                journal_id=rev_journal_id,
                transaction_id=orig.transaction_id,
                account_id=orig.account_id,
                account_type_marker=orig.account_type_marker,
                gl_account_id=orig.gl_account_id,
                entry_type=inverse_type,
                amount=reversal_amount,
                currency=orig.currency,
                original_entry_id=orig.entry_id,
                posting_status=status,
                posted_at=rev_time,
            )
            rev_entries.append(rev_entry)

        rev_journal = JournalRecord(
            journal_id=rev_journal_id,
            transaction_id=original_journal.transaction_id,
            journal_type="REVERSAL",
            description=f"Reversal of {original_journal.journal_id} ({reason})",
            created_at=rev_time,
            entries=rev_entries,
        )
        return rev_journal
