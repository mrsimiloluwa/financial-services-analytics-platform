"""Configuration profiles, chart-of-accounts definitions, and accounting policies for the synthetic generator."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class GLAccountDefinition(BaseModel):
    """General Ledger account specification for the internal bank chart of accounts."""

    gl_account_id: str
    gl_account_number: str
    account_name: str
    account_category: Literal["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]
    normal_balance: Literal["DEBIT", "CREDIT"]
    currency: str
    description: str


# Governed Master Chart of Accounts
STANDARD_GL_ACCOUNTS: list[GLAccountDefinition] = [
    # Asset Accounts (Normal Balance: DEBIT)
    GLAccountDefinition(
        gl_account_id="GL_ASSET_CENTRAL_BANK",
        gl_account_number="1010",
        account_name="Central Bank Reserve & Settlement",
        account_category="ASSET",
        normal_balance="DEBIT",
        currency="EUR",
        description="Settlement clearing funds held at central bank/clearing house",
    ),
    GLAccountDefinition(
        gl_account_id="GL_ASSET_NOSTRO_CLEARING",
        gl_account_number="1020",
        account_name="Nostro Correspondent Clearing",
        account_category="ASSET",
        normal_balance="DEBIT",
        currency="EUR",
        description="Correspondent bank accounts for cross-border wire settlements",
    ),
    GLAccountDefinition(
        gl_account_id="GL_ASSET_FX_CLEARING",
        gl_account_number="1030",
        account_name="Foreign Exchange Clearing Position",
        account_category="ASSET",
        normal_balance="DEBIT",
        currency="EUR",
        description="Multi-currency clearing account ensuring balanced per-currency legs on FX trades",
    ),
    GLAccountDefinition(
        gl_account_id="GL_ASSET_CUSTOMER_OVERDRAFTS",
        gl_account_number="1040",
        account_name="Customer Overdraft Lending Assets",
        account_category="ASSET",
        normal_balance="DEBIT",
        currency="EUR",
        description="Asset representing credit drawn by customers under authorized overdraft facilities",
    ),
    # Liability Accounts (Normal Balance: CREDIT)
    GLAccountDefinition(
        gl_account_id="GL_LIAB_CUSTOMER_DEPOSITS",
        gl_account_number="2010",
        account_name="Customer Demand Deposits",
        account_category="LIABILITY",
        normal_balance="CREDIT",
        currency="EUR",
        description="Aggregated customer deposit liabilities across all currencies",
    ),
    GLAccountDefinition(
        gl_account_id="GL_LIAB_RESERVED_FUNDS",
        gl_account_number="2020",
        account_name="Customer Reserved & Held Funds",
        account_category="LIABILITY",
        normal_balance="CREDIT",
        currency="EUR",
        description="Uncleared pre-authorizations and settlement holds",
    ),
    # Equity Accounts (Normal Balance: CREDIT)
    GLAccountDefinition(
        gl_account_id="GL_EQUITY_RETAINED_EARNINGS",
        gl_account_number="3010",
        account_name="Retained Earnings & Bank Capital",
        account_category="EQUITY",
        normal_balance="CREDIT",
        currency="EUR",
        description="Accumulated bank net earnings and tier-1 capital reserves",
    ),
    # Revenue Accounts (Normal Balance: CREDIT, unless Contra-Revenue: DEBIT)
    GLAccountDefinition(
        gl_account_id="GL_REV_WIRE_FEES",
        gl_account_number="4010",
        account_name="Wire Transfer Fee Revenue",
        account_category="REVENUE",
        normal_balance="CREDIT",
        currency="EUR",
        description="Collected domestic and international wire transfer service fees",
    ),
    GLAccountDefinition(
        gl_account_id="GL_REV_ACH_FEES",
        gl_account_number="4020",
        account_name="ACH & Direct Debit Fee Revenue",
        account_category="REVENUE",
        normal_balance="CREDIT",
        currency="EUR",
        description="Batch payment and direct debit processing fee income",
    ),
    GLAccountDefinition(
        gl_account_id="GL_REV_CARD_FEES",
        gl_account_number="4030",
        account_name="Card Interchange & Settlement Fee Revenue",
        account_category="REVENUE",
        normal_balance="CREDIT",
        currency="EUR",
        description="Merchant discount and card interchange fee revenue",
    ),
    GLAccountDefinition(
        gl_account_id="GL_REV_FX_SPREAD",
        gl_account_number="4040",
        account_name="Foreign Exchange Margin & Spread Income",
        account_category="REVENUE",
        normal_balance="CREDIT",
        currency="EUR",
        description="Realized bid/ask spread and FX conversion margin income",
    ),
    GLAccountDefinition(
        gl_account_id="GL_REV_OVERDRAFT_INTEREST",
        gl_account_number="4050",
        account_name="Overdraft Interest & Facility Income",
        account_category="REVENUE",
        normal_balance="CREDIT",
        currency="EUR",
        description="Periodic interest charges debited from accounts with negative balances",
    ),
    GLAccountDefinition(
        gl_account_id="GL_CONTRA_REV_WAIVERS",
        gl_account_number="4090",
        account_name="Fee Waivers & Pricing Concessions",
        account_category="REVENUE",
        normal_balance="DEBIT",
        currency="EUR",
        description="Contra-revenue reducing gross fee revenue for contractual discounts or concessions",
    ),
    # Expense Accounts (Normal Balance: DEBIT)
    GLAccountDefinition(
        gl_account_id="GL_EXP_NETWORK_COSTS",
        gl_account_number="5010",
        account_name="Payment Network Pass-Through Expense",
        account_category="EXPENSE",
        normal_balance="DEBIT",
        currency="EUR",
        description="Direct external network switch and card scheme costs paid to external clearing rails",
    ),
]


class GeneratorConfig(BaseModel):
    """Configuration governing synthetic dataset generation."""

    seed: int = Field(default=42, description="Random seed for deterministic generation")
    profile: Literal["TEST", "DEV", "DEMO"] = Field(
        default="DEV",
        description="Predefined generation volume scale",
    )
    reporting_base_currency: Literal["EUR", "USD", "GBP"] = Field(
        default="EUR",
        description="Base currency for centralized reporting and FX conversion",
    )
    start_date: date = Field(default=date(2025, 1, 1), description="Start of historical period")
    end_date: date = Field(default=date(2025, 12, 31), description="End of historical period")

    # Volume parameters
    customer_count: int = Field(default=50, ge=1)
    accounts_per_customer_min: int = Field(default=1, ge=1)
    accounts_per_customer_max: int = Field(default=4, ge=1)
    transaction_count: int = Field(default=5000, ge=1)

    # Currency domain distinction:
    # 1. Supported Account Currencies: Currencies in which customer bank accounts can be opened.
    supported_account_currencies: list[str] = Field(
        default_factory=lambda: ["EUR", "USD", "GBP", "CHF"],
        description="Permitted ISO-4217 currencies for customer account creation",
    )
    # 2. Supported Reporting Base Currencies: Currencies permitted as reporting denominators.
    supported_reporting_currencies: list[str] = Field(
        default_factory=lambda: ["EUR", "USD", "GBP"],
        description="Permitted ISO-4217 reporting currencies",
    )

    @classmethod
    def get_profile(
        cls,
        profile: Literal["TEST", "DEV", "DEMO"],
        seed: int = 42,
        reporting_base_currency: Literal["EUR", "USD", "GBP"] = "EUR",
    ) -> "GeneratorConfig":
        """Factory creating preset configuration profiles."""
        if profile == "TEST":
            return cls(
                seed=seed,
                profile="TEST",
                reporting_base_currency=reporting_base_currency,
                customer_count=10,
                transaction_count=200,
            )
        if profile == "DEMO":
            return cls(
                seed=seed,
                profile="DEMO",
                reporting_base_currency=reporting_base_currency,
                customer_count=1000,
                transaction_count=100000,
            )
        # Default DEV profile
        return cls(
            seed=seed,
            profile="DEV",
            reporting_base_currency=reporting_base_currency,
            customer_count=50,
            transaction_count=5000,
        )
