"""Commercial transaction engine generating realistic payments, wires, card settlements, and FX conversions."""

import random
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from data_platform.generator.config import GeneratorConfig
from data_platform.generator.engines.fx_engine import FXEngine
from data_platform.generator.engines.ledger_engine import LedgerEngine
from data_platform.generator.schemas import (
    AccountRecord,
    CustomerRecord,
    JournalRecord,
    LedgerEntryRecord,
    TransactionRecord,
)


class TransactionEngine:
    """Generates commercial transactions and coordinates double-entry ledger postings."""

    TRANSACTION_CHANNELS: dict[str, list[str]] = {
        "WIRE_TRANSFER": ["SWIFT", "ONLINE_BANKING"],
        "ACH_PAYMENT": ["SEPA_CORE", "API_GATEWAY"],
        "CARD_SETTLEMENT": ["API_GATEWAY", "ONLINE_BANKING"],
        "FX_CONVERSION": ["SWIFT", "ONLINE_BANKING"],
    }

    def __init__(
        self,
        config: GeneratorConfig | None = None,
        fx_engine: FXEngine | None = None,
        ledger_engine: LedgerEngine | None = None,
    ) -> None:
        self.config = config or GeneratorConfig.get_profile("DEV")
        self.rng = random.Random(self.config.seed)
        self.fx_engine = fx_engine or FXEngine(
            seed=self.config.seed,
            reporting_base_currency=self.config.reporting_base_currency,
        )
        self.ledger_engine = ledger_engine or LedgerEngine(fx_engine=self.fx_engine)
        self.txn_counter = 1

    def generate_transactions_and_journals(
        self,
        customers: list[CustomerRecord],
        accounts: list[AccountRecord],
    ) -> tuple[list[TransactionRecord], list[JournalRecord], list[LedgerEntryRecord]]:
        """Generate transactions and corresponding balanced double-entry accounting journals."""
        transactions: list[TransactionRecord] = []
        journals: list[JournalRecord] = []
        all_ledger_entries: list[LedgerEntryRecord] = []

        # Index accounts by customer_id and currency
        customer_map = {c.customer_id: c for c in customers}
        accounts_by_cust: dict[str, list[AccountRecord]] = {}
        for acc in accounts:
            accounts_by_cust.setdefault(acc.customer_id, []).append(acc)

        active_accounts = [a for a in accounts if a.status == "ACTIVE"]
        if not active_accounts:
            raise ValueError("Cannot generate transactions without active accounts")

        total_days = max(1, (self.config.end_date - self.config.start_date).days)

        for _ in range(self.config.transaction_count):
            source_acc = self.rng.choice(active_accounts)
            cust = customer_map[source_acc.customer_id]

            # Determine transaction type based on customer segment
            if cust.customer_segment == "INSTITUTIONAL":
                txn_type = self.rng.choices(
                    ["WIRE_TRANSFER", "FX_CONVERSION", "ACH_PAYMENT"],
                    weights=[0.50, 0.40, 0.10],
                    k=1,
                )[0]
                amount = Decimal(str(self.rng.randint(50_000, 1_500_000)))
            elif cust.customer_segment == "COMMERCIAL_SME":
                txn_type = self.rng.choices(
                    ["ACH_PAYMENT", "WIRE_TRANSFER", "CARD_SETTLEMENT", "FX_CONVERSION"],
                    weights=[0.45, 0.30, 0.15, 0.10],
                    k=1,
                )[0]
                amount = Decimal(str(self.rng.randint(2_000, 80_000)))
            else:  # RETAIL_WEALTH
                txn_type = self.rng.choices(
                    ["CARD_SETTLEMENT", "ACH_PAYMENT", "WIRE_TRANSFER", "FX_CONVERSION"],
                    weights=[0.55, 0.30, 0.10, 0.05],
                    k=1,
                )[0]
                amount = Decimal(str(self.rng.randint(25, 4_500)))

            amount = amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
            txn_currency = source_acc.currency

            # Multi-currency routing for FX_CONVERSION
            dest_acc: AccountRecord | None = None
            if txn_type == "FX_CONVERSION":
                # Look for another account owned by same customer with different currency
                cust_accounts = accounts_by_cust.get(cust.customer_id, [])
                other_curr_accounts = [
                    a for a in cust_accounts if a.currency != txn_currency and a.status == "ACTIVE"
                ]
                if other_curr_accounts:
                    dest_acc = self.rng.choice(other_curr_accounts)
                    settlement_currency = dest_acc.currency
                else:
                    # Counterparty in different currency
                    available_other = [a for a in active_accounts if a.currency != txn_currency]
                    dest_acc = self.rng.choice(available_other) if available_other else None
                    settlement_currency = dest_acc.currency if dest_acc else "USD"
            else:
                settlement_currency = txn_currency
                # 30% chance of internal counterparty transfer, 70% external clearing
                if self.rng.random() < 0.30:
                    same_curr_accounts = [
                        a
                        for a in active_accounts
                        if a.account_id != source_acc.account_id and a.currency == txn_currency
                    ]
                    dest_acc = self.rng.choice(same_curr_accounts) if same_curr_accounts else None

            # Timestamp within simulation date range
            day_offset = self.rng.randint(0, total_days)
            txn_date = self.config.start_date + timedelta(days=day_offset)
            minute_offset = self.rng.randint(0, 86399)
            initiated_at = datetime.combine(txn_date, time(0, 0), tzinfo=UTC) + timedelta(
                seconds=minute_offset
            )

            # FX rate resolution
            if txn_currency == settlement_currency:
                customer_fx_rate = Decimal("1.000000")
            else:
                mid_rate = self.fx_engine.get_mid_rate(txn_currency, settlement_currency, txn_date)
                # Customer rate applies a 20 bps bank margin
                margin = Decimal("0.002000")
                customer_fx_rate = (mid_rate * (Decimal("1.000000") - margin)).quantize(
                    Decimal("0.000001"),
                    rounding=ROUND_HALF_EVEN,
                )

            # Convert to reporting base currency (EUR)
            base_currency_amount = self.fx_engine.convert_to_reporting_base(
                amount=amount,
                from_currency=txn_currency,
                rate_date=txn_date,
            )

            # Status distribution: 92% SETTLED, 4% PENDING, 3% FAILED, 1% REVERSED
            simulation_end_dt = datetime.combine(self.config.end_date, time(23, 59, 59), tzinfo=UTC)
            status_dice = self.rng.random()
            if status_dice < 0.92:
                status = "SETTLED"
                raw_settled = initiated_at + timedelta(minutes=self.rng.randint(2, 60))
                settled_at = min(raw_settled, simulation_end_dt)
            elif status_dice < 0.96:
                status = "PENDING"
                settled_at = None
            elif status_dice < 0.99:
                status = "FAILED"
                settled_at = None
            else:
                status = "REVERSED"
                raw_settled = initiated_at + timedelta(minutes=15)
                settled_at = min(raw_settled, simulation_end_dt)

            channel = self.rng.choice(self.TRANSACTION_CHANNELS[txn_type])
            # Direction: Card settlements and FX conversions are always customer DEBITs.
            # Wire transfers and ACH payments support two-way customer flows (~70% DEBIT outbound, ~30% CREDIT inbound).
            if txn_type in ("CARD_SETTLEMENT", "FX_CONVERSION"):
                direction = "DEBIT"
            else:
                direction = "CREDIT" if self.rng.random() < 0.30 else "DEBIT"

            txn_id = f"TXN_{self.txn_counter:08d}"
            self.txn_counter += 1

            transaction = TransactionRecord(
                transaction_id=txn_id,
                account_id=source_acc.account_id,
                counterparty_account_id=dest_acc.account_id if dest_acc else None,
                transaction_type=txn_type,
                channel=channel,
                direction=direction,
                transaction_amount=amount,
                transaction_currency=txn_currency,
                settlement_currency=settlement_currency,
                customer_fx_rate=customer_fx_rate,
                base_currency_amount=base_currency_amount,
                status=status,
                initiated_at=initiated_at,
                settled_at=settled_at,
            )
            transactions.append(transaction)

            # Double-entry ledger integration: Only SETTLED or REVERSED transactions post to ledger
            if status in ("SETTLED", "REVERSED"):
                journal = self.ledger_engine.create_settlement_journal(
                    transaction=transaction,
                    source_account=source_acc,
                    counterparty_account=dest_acc,
                )
                transaction.journal_id = journal.journal_id
                journals.append(journal)
                all_ledger_entries.extend(journal.entries)

                # For REVERSED transactions, create an append-only reversal journal
                if status == "REVERSED":
                    rev_time = (settled_at or initiated_at) + timedelta(
                        hours=self.rng.randint(1, 48)
                    )
                    rev_journal = self.ledger_engine.create_reversal_journal(
                        original_journal=journal,
                        reversal_percentage=Decimal("1.0000"),
                        reversal_timestamp=rev_time,
                        reason="TRANSACTION_REVERSAL_CUSTOMER_REQUEST",
                    )
                    journals.append(rev_journal)
                    all_ledger_entries.extend(rev_journal.entries)

        return transactions, journals, all_ledger_entries
