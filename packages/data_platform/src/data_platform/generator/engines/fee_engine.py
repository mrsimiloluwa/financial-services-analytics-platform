"""Fee assessment and collection engine enforcing pricing schedules, waivers, and collection lifecycles."""

from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from data_platform.generator.engines.ledger_engine import LedgerEngine
from data_platform.generator.schemas import (
    AccountRecord,
    FeeAssessmentRecord,
    FeeCollectionRecord,
    JournalRecord,
    LedgerEntryRecord,
    RevenueRecognitionRecord,
    TransactionRecord,
)


class PricingRule:
    """Pricing schedule definition for a transaction type and customer segment."""

    def __init__(
        self,
        rule_id: str,
        transaction_type: str,
        customer_segment: str | None,
        base_fee: Decimal,
        basis_points: Decimal,  # e.g., Decimal("0.0015") = 15 bps
        currency: str,
        effective_start: date,
        effective_end: date,
        description: str,
        is_override: bool = False,
    ) -> None:
        self.rule_id = rule_id
        self.transaction_type = transaction_type
        self.customer_segment = customer_segment
        self.base_fee = base_fee
        self.basis_points = basis_points
        self.currency = currency
        self.effective_start = effective_start
        self.effective_end = effective_end
        self.description = description
        self.is_override = is_override


# Standard Governed Fee Catalogue
STANDARD_PRICING_CATALOGUE: list[PricingRule] = [
    # Wire Transfers
    PricingRule(
        rule_id="RULE_WIRE_INSTITUTIONAL",
        transaction_type="WIRE_TRANSFER",
        customer_segment="INSTITUTIONAL",
        base_fee=Decimal("15.0000"),
        basis_points=Decimal("0.0005"),  # 5 bps
        currency="EUR",
        effective_start=date(2025, 1, 1),
        effective_end=date(2025, 12, 31),
        description="Institutional wholesale wire schedule",
    ),
    PricingRule(
        rule_id="RULE_WIRE_COMMERCIAL",
        transaction_type="WIRE_TRANSFER",
        customer_segment="COMMERCIAL_SME",
        base_fee=Decimal("10.0000"),
        basis_points=Decimal("0.0010"),  # 10 bps
        currency="EUR",
        effective_start=date(2025, 1, 1),
        effective_end=date(2025, 12, 31),
        description="Commercial SME corporate wire schedule",
    ),
    PricingRule(
        rule_id="RULE_WIRE_RETAIL",
        transaction_type="WIRE_TRANSFER",
        customer_segment="RETAIL_WEALTH",
        base_fee=Decimal("5.0000"),
        basis_points=Decimal("0.0015"),  # 15 bps
        currency="EUR",
        effective_start=date(2025, 1, 1),
        effective_end=date(2025, 12, 31),
        description="Retail wealth outgoing wire schedule",
    ),
    # ACH Payments
    PricingRule(
        rule_id="RULE_ACH_STANDARD",
        transaction_type="ACH_PAYMENT",
        customer_segment=None,  # Generic default
        base_fee=Decimal("0.5000"),
        basis_points=Decimal("0.0000"),
        currency="EUR",
        effective_start=date(2025, 1, 1),
        effective_end=date(2025, 12, 31),
        description="Standard batch SEPA ACH fee",
    ),
    # Card Settlements
    PricingRule(
        rule_id="RULE_CARD_MERCHANT",
        transaction_type="CARD_SETTLEMENT",
        customer_segment=None,
        base_fee=Decimal("0.2000"),
        basis_points=Decimal("0.0120"),  # 120 bps interchange/merchant discount
        currency="EUR",
        effective_start=date(2025, 1, 1),
        effective_end=date(2025, 12, 31),
        description="Card merchant processing interchange fee",
    ),
]


class FeeEngine:
    """Evaluates pricing schedules, calculates waivers, executes collections, and generates fee journals."""

    FEE_REVENUE_GL_MAP: dict[str, str] = {
        "WIRE_TRANSFER": "GL_REV_WIRE_FEES",
        "ACH_PAYMENT": "GL_REV_ACH_FEES",
        "CARD_SETTLEMENT": "GL_REV_CARD_FEES",
        "FX_CONVERSION": "GL_REV_FX_SPREAD",
    }

    def __init__(
        self,
        pricing_catalogue: list[PricingRule] | None = None,
        overrides: list[PricingRule] | None = None,
        ledger_engine: LedgerEngine | None = None,
    ) -> None:
        self.catalogue = pricing_catalogue or list(STANDARD_PRICING_CATALOGUE)
        self.overrides = overrides or []
        self.ledger_engine = ledger_engine or LedgerEngine()
        self.assessment_counter = 1
        self.collection_counter = 1
        self.recognition_counter = 1
        # Track cumulative collections per assessment: assessment_id -> Decimal
        self.cumulative_collections: dict[str, Decimal] = {}

    def _next_assessment_id(self) -> str:
        aid = f"FA_{self.assessment_counter:08d}"
        self.assessment_counter += 1
        return aid

    def _next_collection_id(self) -> str:
        cid = f"FC_{self.collection_counter:08d}"
        self.collection_counter += 1
        return cid

    def _next_recognition_id(self) -> str:
        rid = f"RR_{self.recognition_counter:08d}"
        self.recognition_counter += 1
        return rid

    def resolve_pricing_rule(
        self,
        transaction_type: str,
        customer_segment: str | None,
        pricing_date: date,
        account_id: str | None = None,
    ) -> PricingRule | None:
        """Deterministically resolve the applicable pricing rule, prioritizing active contractual overrides."""
        # Check overrides first
        for rule in self.overrides:
            if (
                rule.transaction_type == transaction_type
                and (rule.customer_segment is None or rule.customer_segment == customer_segment)
                and rule.effective_start <= pricing_date <= rule.effective_end
            ):
                return rule

        # Standard catalogue: exact segment match first, then generic default
        best_match: PricingRule | None = None
        for rule in self.catalogue:
            if (
                rule.transaction_type == transaction_type
                and rule.effective_start <= pricing_date <= rule.effective_end
            ):
                if rule.customer_segment == customer_segment:
                    return rule  # Exact segment priority
                if rule.customer_segment is None and best_match is None:
                    best_match = rule  # Fallback generic default

        return best_match

    def assess_fee(
        self,
        transaction: TransactionRecord,
        customer_segment: str | None = None,
        waiver_percentage: Decimal = Decimal("0.0000"),
        waiver_reason: str | None = None,
    ) -> FeeAssessmentRecord | None:
        """Assess gross and net collectible fee for a transaction."""
        txn_date = (transaction.settled_at or transaction.initiated_at).date()
        rule = self.resolve_pricing_rule(
            transaction_type=transaction.transaction_type,
            customer_segment=customer_segment,
            pricing_date=txn_date,
            account_id=transaction.account_id,
        )
        if not rule:
            return None

        # Gross Assessed Fee = base fee + (transaction_amount * basis_points)
        var_fee = (transaction.transaction_amount * rule.basis_points).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        )
        gross_fee = (rule.base_fee + var_fee).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)

        # Apply waiver
        waiver_pct = min(max(waiver_percentage, Decimal("0.0000")), Decimal("1.0000"))
        waived_amount = (gross_fee * waiver_pct).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        )
        net_collectible = gross_fee - waived_amount

        if waived_amount == gross_fee:
            status: Literal["ASSESSED", "WAIVED_IN_FULL", "PARTIALLY_WAIVED"] = "WAIVED_IN_FULL"
        elif waived_amount > Decimal("0.0000"):
            status = "PARTIALLY_WAIVED"
        else:
            status = "ASSESSED"

        assessment = FeeAssessmentRecord(
            assessment_id=self._next_assessment_id(),
            transaction_id=transaction.transaction_id,
            account_id=transaction.account_id,
            gross_assessed_amount=gross_fee,
            waived_amount=waived_amount,
            waiver_reason=waiver_reason if waived_amount > Decimal("0.0000") else None,
            net_collectible_amount=net_collectible,
            assessment_status=status,
            assessed_at=transaction.settled_at or transaction.initiated_at,
        )
        return assessment

    def execute_collection_attempt(
        self,
        assessment: FeeAssessmentRecord,
        account: AccountRecord,
        attempt_number: int = 1,
        collected_amount: Decimal | None = None,
        force_fail: bool = False,
        failure_reason: str | None = None,
        attempt_timestamp: datetime | None = None,
        pass_through_cost: Decimal = Decimal("0.0000"),
        transaction_type: str = "WIRE_TRANSFER",
    ) -> tuple[FeeCollectionRecord, JournalRecord | None, RevenueRecognitionRecord | None]:
        """Execute a fee collection sweep against customer balance, enforcing double-entry postings and collection ceilings."""
        timestamp = attempt_timestamp or assessment.assessed_at
        current_cumulative = self.cumulative_collections.get(
            assessment.assessment_id, Decimal("0.0000")
        )
        remaining_collectible = assessment.net_collectible_amount - current_cumulative

        if remaining_collectible <= Decimal("0.0000"):
            raise ValueError(
                f"Assessment {assessment.assessment_id} is already fully collected (remaining: {remaining_collectible})"
            )

        target = remaining_collectible.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
        collection_id = self._next_collection_id()

        # Handle explicit failure (e.g., customer account frozen or insufficient funds)
        if force_fail or account.status == "FROZEN":
            reason = failure_reason or (
                "ACCOUNT_FROZEN" if account.status == "FROZEN" else "INSUFFICIENT_FUNDS"
            )
            record = FeeCollectionRecord(
                collection_id=collection_id,
                assessment_id=assessment.assessment_id,
                account_id=assessment.account_id,
                collection_attempt_number=attempt_number,
                target_amount=target,
                collected_amount=Decimal("0.0000"),
                outstanding_amount=target,
                collection_status="FAILED",
                failure_reason=reason,
                attempted_at=timestamp,
                settled_at=None,
                linked_ledger_entry_id=None,
            )
            return record, None, None

        # Execute successful or partial collection
        actual_collected = (collected_amount if collected_amount is not None else target).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        )

        if actual_collected > target:
            raise ValueError(
                f"Cannot collect {actual_collected} exceeding target {target} for assessment {assessment.assessment_id}"
            )

        outstanding = (target - actual_collected).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        )
        status: Literal["SETTLED", "PARTIAL", "FAILED", "REVERSED"] = (
            "SETTLED" if outstanding == Decimal("0.0000") else "PARTIAL"
        )

        # Update cumulative collection tracking
        self.cumulative_collections[assessment.assessment_id] = (
            current_cumulative + actual_collected
        )

        # Construct balanced double-entry accounting journal for collected fees:
        # DEBIT: Customer Deposits (Liability decreases as bank debits fee from customer)
        # CREDIT: Fee Revenue GL Account (Revenue increases)
        journal_id = self.ledger_engine._next_journal_id()
        debit_entry_id = self.ledger_engine._next_entry_id()
        credit_entry_id = self.ledger_engine._next_entry_id()
        fee_revenue_gl = self.FEE_REVENUE_GL_MAP.get(transaction_type, "GL_REV_WIRE_FEES")

        entries = [
            LedgerEntryRecord(
                entry_id=debit_entry_id,
                journal_id=journal_id,
                transaction_id=assessment.transaction_id,
                account_id=account.account_id,
                account_type_marker="CUSTOMER",
                gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
                entry_type="DEBIT",
                amount=actual_collected,
                currency=account.currency,
                posted_at=timestamp,
            ),
            LedgerEntryRecord(
                entry_id=credit_entry_id,
                journal_id=journal_id,
                transaction_id=assessment.transaction_id,
                account_id=fee_revenue_gl,
                account_type_marker="GL_INTERNAL",
                gl_account_id=fee_revenue_gl,
                entry_type="CREDIT",
                amount=actual_collected,
                currency=account.currency,
                posted_at=timestamp,
            ),
        ]

        journal = JournalRecord(
            journal_id=journal_id,
            transaction_id=assessment.transaction_id,
            journal_type="FEE_SETTLEMENT",
            description=f"Fee collection for assessment {assessment.assessment_id}",
            created_at=timestamp,
            entries=entries,
        )

        collection_record = FeeCollectionRecord(
            collection_id=collection_id,
            assessment_id=assessment.assessment_id,
            account_id=assessment.account_id,
            collection_attempt_number=attempt_number,
            target_amount=target,
            collected_amount=actual_collected,
            outstanding_amount=outstanding,
            collection_status=status,
            failure_reason=None,
            attempted_at=timestamp,
            settled_at=timestamp,
            linked_ledger_entry_id=debit_entry_id,
        )

        # Revenue recognition record
        net_revenue = actual_collected - pass_through_cost
        recognition_record = RevenueRecognitionRecord(
            recognition_id=self._next_recognition_id(),
            collection_id=collection_id,
            gross_collected_revenue=actual_collected,
            reversed_revenue_amount=Decimal("0.0000"),
            pass_through_cost=pass_through_cost,
            net_recognized_revenue=net_revenue,
            recognized_at=timestamp,
        )

        return collection_record, journal, recognition_record
