"""Pydantic v2 domain schemas validating financial and accounting entity records."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class GLAccountRecord(BaseModel):
    """Internal bank General Ledger master account record."""

    gl_account_id: str = Field(..., min_length=3, max_length=64)
    gl_account_number: str = Field(..., min_length=4, max_length=16)
    account_name: str = Field(..., min_length=3, max_length=255)
    account_category: Literal["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]
    normal_balance: Literal["DEBIT", "CREDIT"]
    currency: str = Field(..., min_length=3, max_length=3)
    description: str


class CustomerRecord(BaseModel):
    """Customer profile record."""

    customer_id: str = Field(..., min_length=3, max_length=64)
    legal_entity_id: str = Field(..., min_length=3, max_length=64)
    customer_name: str = Field(..., min_length=2, max_length=255)
    customer_segment: Literal["RETAIL_WEALTH", "COMMERCIAL_SME", "INSTITUTIONAL"]
    status: Literal["ACTIVE", "SUSPENDED", "CLOSED"]
    onboarding_date: date


class AccountRecord(BaseModel):
    """Customer bank account record."""

    account_id: str = Field(..., min_length=3, max_length=64)
    customer_id: str = Field(..., min_length=3, max_length=64)
    account_number: str = Field(..., min_length=5, max_length=64)
    account_type: Literal["OPERATING_CHECKING", "TREASURY_SWEEP", "MERCHANT_SETTLEMENT"]
    currency: str = Field(..., min_length=3, max_length=3)
    opening_balance: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    reserved_funds: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    status: Literal["ACTIVE", "FROZEN", "CLOSED"]
    opened_at: datetime


class OverdraftFacilityRecord(BaseModel):
    """Contractual overdraft limit and terms attached to an account."""

    facility_id: str = Field(..., min_length=3, max_length=64)
    account_id: str = Field(..., min_length=3, max_length=64)
    authorized_limit: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    standard_interest_rate: Decimal = Field(..., ge=Decimal("0.0000"), le=Decimal("1.0000"))
    unauthorized_penalty_rate: Decimal = Field(..., ge=Decimal("0.0000"), le=Decimal("1.0000"))
    effective_start_date: date
    effective_end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "OverdraftFacilityRecord":
        if self.effective_end_date < self.effective_start_date:
            raise ValueError("effective_end_date cannot be earlier than effective_start_date")
        return self


class FXRateRecord(BaseModel):
    """Exchange rate matrix entry."""

    rate_id: str = Field(..., min_length=3, max_length=64)
    rate_date: date
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)
    mid_rate: Decimal = Field(..., gt=Decimal("0.000000"))
    bid_rate: Decimal = Field(..., gt=Decimal("0.000000"))
    ask_rate: Decimal = Field(..., gt=Decimal("0.000000"))
    rate_source: str = Field(..., min_length=2, max_length=64)
    rate_type: Literal["SPOT", "HISTORICAL_EOD"]
    rate_timestamp: datetime

    @model_validator(mode="after")
    def validate_spread(self) -> "FXRateRecord":
        if self.bid_rate > self.mid_rate:
            raise ValueError(f"Bid rate ({self.bid_rate}) cannot exceed mid rate ({self.mid_rate})")
        if self.ask_rate < self.mid_rate:
            raise ValueError(
                f"Ask rate ({self.ask_rate}) cannot be less than mid rate ({self.mid_rate})"
            )
        return self


class TransactionRecord(BaseModel):
    """Commercial financial business transaction."""

    transaction_id: str = Field(..., min_length=3, max_length=64)
    account_id: str = Field(..., min_length=3, max_length=64)
    counterparty_account_id: str | None = Field(default=None, max_length=64)
    transaction_type: Literal[
        "WIRE_TRANSFER",
        "ACH_PAYMENT",
        "CARD_SETTLEMENT",
        "FX_CONVERSION",
        "INTEREST_POSTING",
    ]
    channel: Literal["ONLINE_BANKING", "API_GATEWAY", "SWIFT", "SEPA_CORE"]
    direction: Literal["DEBIT", "CREDIT"]
    transaction_amount: Decimal = Field(..., gt=Decimal("0.0000"))
    transaction_currency: str = Field(..., min_length=3, max_length=3)
    settlement_currency: str = Field(..., min_length=3, max_length=3)
    customer_fx_rate: Decimal = Field(default=Decimal("1.000000"), gt=Decimal("0.000000"))
    base_currency_amount: Decimal = Field(..., gt=Decimal("0.0000"))
    status: Literal["SETTLED", "PENDING", "REVERSED", "FAILED"]
    original_transaction_id: str | None = Field(default=None, max_length=64)
    journal_id: str | None = Field(default=None, max_length=64)
    initiated_at: datetime
    settled_at: datetime | None = None


class LedgerEntryRecord(BaseModel):
    """Double-entry general ledger posting record."""

    entry_id: str = Field(..., min_length=3, max_length=64)
    journal_id: str = Field(..., min_length=3, max_length=64)
    transaction_id: str | None = Field(default=None, max_length=64)
    account_id: str = Field(..., min_length=3, max_length=64)
    account_type_marker: Literal["CUSTOMER", "GL_INTERNAL"]
    gl_account_id: str = Field(..., min_length=3, max_length=64)
    entry_type: Literal["DEBIT", "CREDIT"]
    amount: Decimal = Field(..., gt=Decimal("0.0000"))
    currency: str = Field(..., min_length=3, max_length=3)
    original_entry_id: str | None = Field(default=None, max_length=64)
    posting_status: Literal["POSTED", "REVERSED", "PARTIALLY_REVERSED"] = "POSTED"
    posted_at: datetime


class JournalRecord(BaseModel):
    """Accounting journal event grouping balanced double-entry ledger postings."""

    journal_id: str = Field(..., min_length=3, max_length=64)
    transaction_id: str | None = Field(default=None, max_length=64)
    journal_type: Literal[
        "WIRE_SETTLEMENT",
        "ACH_SETTLEMENT",
        "CARD_SETTLEMENT",
        "FX_CONVERSION",
        "REVERSAL",
        "FEE_SETTLEMENT",
        "INTEREST_POSTING",
    ]
    description: str = Field(..., min_length=3, max_length=255)
    created_at: datetime
    entries: list[LedgerEntryRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_double_entry_balance_per_currency(self) -> "JournalRecord":
        """Every completed journal must balance independently for each currency: SUM(DEBITS) == SUM(CREDITS)."""
        if not self.entries:
            return self

        balances: dict[str, Decimal] = {}
        for entry in self.entries:
            curr = entry.currency
            balances.setdefault(curr, Decimal("0.0000"))
            if entry.entry_type == "DEBIT":
                balances[curr] += entry.amount
            elif entry.entry_type == "CREDIT":
                balances[curr] -= entry.amount

        unbalanced = {curr: diff for curr, diff in balances.items() if diff != Decimal("0.0000")}
        if unbalanced:
            raise ValueError(
                f"Journal {self.journal_id} is unbalanced for currency legs: {unbalanced}. "
                "Every currency leg in a journal must balance independently."
            )
        return self


class FeeAssessmentRecord(BaseModel):
    """Record of fee evaluated against a transaction based on pricing schedules."""

    assessment_id: str = Field(..., min_length=3, max_length=64)
    transaction_id: str = Field(..., min_length=3, max_length=64)
    account_id: str = Field(..., min_length=3, max_length=64)
    gross_assessed_amount: Decimal = Field(..., ge=Decimal("0.0000"))
    waived_amount: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    waiver_reason: str | None = Field(default=None, max_length=255)
    net_collectible_amount: Decimal = Field(..., ge=Decimal("0.0000"))
    assessment_status: Literal["ASSESSED", "WAIVED_IN_FULL", "PARTIALLY_WAIVED"]
    assessed_at: datetime

    @model_validator(mode="after")
    def validate_fee_decomposition(self) -> "FeeAssessmentRecord":
        if self.gross_assessed_amount != (self.waived_amount + self.net_collectible_amount):
            raise ValueError(
                f"Gross assessed amount ({self.gross_assessed_amount}) must exactly equal "
                f"waived amount ({self.waived_amount}) + collectible amount ({self.net_collectible_amount})"
            )
        return self


class FeeCollectionRecord(BaseModel):
    """Record of a fee collection execution attempt."""

    collection_id: str = Field(..., min_length=3, max_length=64)
    assessment_id: str = Field(..., min_length=3, max_length=64)
    account_id: str = Field(..., min_length=3, max_length=64)
    collection_attempt_number: int = Field(default=1, ge=1)
    target_amount: Decimal = Field(..., gt=Decimal("0.0000"))
    collected_amount: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    outstanding_amount: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    collection_status: Literal["SETTLED", "PARTIAL", "FAILED", "REVERSED"]
    failure_reason: str | None = Field(default=None, max_length=255)
    attempted_at: datetime
    settled_at: datetime | None = None
    linked_ledger_entry_id: str | None = Field(
        default=None,
        max_length=64,
        description="Links to the debit ledger posting to prevent duplicate postings",
    )

    @model_validator(mode="after")
    def validate_collection_balance(self) -> "FeeCollectionRecord":
        if self.target_amount != (self.collected_amount + self.outstanding_amount):
            raise ValueError(
                f"Target amount ({self.target_amount}) must equal collected ({self.collected_amount}) "
                f"+ outstanding ({self.outstanding_amount})"
            )
        if self.collection_status == "SETTLED" and self.outstanding_amount != Decimal("0.0000"):
            raise ValueError("SETTLED collection cannot have positive outstanding amount")
        return self


class RevenueRecognitionRecord(BaseModel):
    """Accounting revenue recognition entry."""

    recognition_id: str = Field(..., min_length=3, max_length=64)
    collection_id: str = Field(..., min_length=3, max_length=64)
    gross_collected_revenue: Decimal = Field(..., ge=Decimal("0.0000"))
    reversed_revenue_amount: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    pass_through_cost: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    net_recognized_revenue: Decimal
    recognized_at: datetime

    @model_validator(mode="after")
    def validate_net_revenue(self) -> "RevenueRecognitionRecord":
        expected_net = (
            self.gross_collected_revenue - self.reversed_revenue_amount - self.pass_through_cost
        )
        if self.net_recognized_revenue != expected_net:
            raise ValueError(
                f"Net recognized revenue ({self.net_recognized_revenue}) must equal gross "
                f"({self.gross_collected_revenue}) - reversed ({self.reversed_revenue_amount}) "
                f"- costs ({self.pass_through_cost}) = {expected_net}"
            )
        return self


class IngestionBatchManifest(BaseModel):
    """Audit header written on every generator & ingestion execution."""

    batch_id: UUID
    generator_version: str = Field(default="1.0.0")
    random_seed: int
    profile_name: str
    reporting_base_currency: Literal["EUR", "USD", "GBP"] = "EUR"
    total_records: int = Field(ge=0)
    entity_counts: dict[str, int] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime
    status: Literal["STARTED", "COMPLETED", "FAILED"] = "COMPLETED"
