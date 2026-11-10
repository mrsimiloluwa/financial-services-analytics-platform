"""Deterministic generator for multi-currency bank accounts and overdraft facilities."""

import random
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from data_platform.generator.schemas import AccountRecord, CustomerRecord, OverdraftFacilityRecord


class AccountEngine:
    """Generates multi-currency accounts and overdraft agreements linked to customers."""

    ACCOUNT_TYPES: list[str] = [
        "OPERATING_CHECKING",
        "TREASURY_SWEEP",
        "MERCHANT_SETTLEMENT",
    ]

    CURRENCY_WEIGHTS: dict[str, list[float]] = {
        # EUR base preferred, followed by USD, GBP, CHF
        "RETAIL_WEALTH": [0.70, 0.15, 0.10, 0.05],
        "COMMERCIAL_SME": [0.55, 0.25, 0.15, 0.05],
        "INSTITUTIONAL": [0.40, 0.35, 0.15, 0.10],
    }

    def __init__(self, seed: int = 42, supported_currencies: list[str] | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.supported_currencies = supported_currencies or ["EUR", "USD", "GBP", "CHF"]

    def generate_accounts_and_facilities(
        self,
        customers: list[CustomerRecord],
    ) -> tuple[list[AccountRecord], list[OverdraftFacilityRecord]]:
        """Generate accounts and attached overdraft facilities for the provided customers."""
        accounts: list[AccountRecord] = []
        facilities: list[OverdraftFacilityRecord] = []

        account_counter = 1
        facility_counter = 1

        for cust in customers:
            # Determine number of accounts by segment
            if cust.customer_segment == "RETAIL_WEALTH":
                num_accounts = self.rng.randint(1, 2)
            elif cust.customer_segment == "COMMERCIAL_SME":
                num_accounts = self.rng.randint(2, 3)
            else:  # INSTITUTIONAL
                num_accounts = self.rng.randint(3, 4)

            weights = self.CURRENCY_WEIGHTS[cust.customer_segment]

            for acc_idx in range(num_accounts):
                account_id = f"ACC_{account_counter:05d}"
                account_counter += 1

                # Pick currency (first account for customer is always EUR primary)
                if acc_idx == 0:
                    currency = "EUR"
                else:
                    currency = self.rng.choices(self.supported_currencies, weights=weights, k=1)[0]

                # Assign account type
                if cust.customer_segment == "RETAIL_WEALTH":
                    acc_type = "OPERATING_CHECKING"
                elif cust.customer_segment == "COMMERCIAL_SME":
                    acc_type = "MERCHANT_SETTLEMENT" if acc_idx == 1 else "OPERATING_CHECKING"
                else:
                    acc_type = "TREASURY_SWEEP" if acc_idx > 1 else "OPERATING_CHECKING"

                # Assign realistic opening balance by segment
                if cust.customer_segment == "RETAIL_WEALTH":
                    bal = Decimal(str(self.rng.randint(5_000, 45_000)))
                elif cust.customer_segment == "COMMERCIAL_SME":
                    bal = Decimal(str(self.rng.randint(50_000, 400_000)))
                else:
                    bal = Decimal(str(self.rng.randint(500_000, 5_000_000)))

                opening_balance = bal.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)

                # Reserved funds (holds / uncleared): 0% to 4% of balance
                hold_pct = Decimal(str(round(self.rng.uniform(0.00, 0.04), 4)))
                reserved_funds = (opening_balance * hold_pct).quantize(
                    Decimal("0.0001"),
                    rounding=ROUND_HALF_EVEN,
                )

                # IBAN-like account number
                country = (
                    "DE"
                    if cust.legal_entity_id == "ENTITY_EU_CENTRAL"
                    else ("GB" if cust.legal_entity_id == "ENTITY_UK_LTD" else "US")
                )
                account_number = f"{country}{self.rng.randint(10, 99)}BANK{self.rng.randint(1000000000, 9999999999)}"

                opened_at = datetime.combine(
                    cust.onboarding_date + timedelta(days=acc_idx),
                    time(9, 0),
                    tzinfo=UTC,
                )

                # Map customer status to account status (suspended customer -> frozen account)
                acc_status = "FROZEN" if cust.status == "SUSPENDED" else cust.status

                account = AccountRecord(
                    account_id=account_id,
                    customer_id=cust.customer_id,
                    account_number=account_number,
                    account_type=acc_type,
                    currency=currency,
                    opening_balance=opening_balance,
                    reserved_funds=reserved_funds,
                    status=acc_status,
                    opened_at=opened_at,
                )
                accounts.append(account)

                # Determine overdraft facility eligibility
                has_facility = False
                if cust.customer_segment == "INSTITUTIONAL":
                    has_facility = True
                elif cust.customer_segment == "COMMERCIAL_SME":
                    has_facility = self.rng.random() < 0.80
                else:  # RETAIL_WEALTH
                    has_facility = self.rng.random() < 0.30

                if has_facility and cust.status == "ACTIVE":
                    if cust.customer_segment == "INSTITUTIONAL":
                        limit = Decimal(str(self.rng.randint(500_000, 2_000_000)))
                        std_rate = Decimal(str(round(self.rng.uniform(0.0450, 0.0650), 4)))
                        pen_rate = Decimal(str(round(self.rng.uniform(0.1200, 0.1500), 4)))
                    elif cust.customer_segment == "COMMERCIAL_SME":
                        limit = Decimal(str(self.rng.randint(25_000, 150_000)))
                        std_rate = Decimal(str(round(self.rng.uniform(0.0750, 0.0950), 4)))
                        pen_rate = Decimal(str(round(self.rng.uniform(0.1600, 0.1900), 4)))
                    else:  # RETAIL_WEALTH
                        limit = Decimal(str(self.rng.randint(2_000, 8_000)))
                        std_rate = Decimal(str(round(self.rng.uniform(0.0900, 0.1200), 4)))
                        pen_rate = Decimal(str(round(self.rng.uniform(0.2000, 0.2400), 4)))

                    eff_start = cust.onboarding_date
                    eff_end = eff_start + timedelta(days=365)

                    facility = OverdraftFacilityRecord(
                        facility_id=f"ODF_{facility_counter:05d}",
                        account_id=account.account_id,
                        authorized_limit=limit.quantize(Decimal("0.0001")),
                        standard_interest_rate=std_rate,
                        unauthorized_penalty_rate=pen_rate,
                        effective_start_date=eff_start,
                        effective_end_date=eff_end,
                    )
                    facilities.append(facility)
                    facility_counter += 1

        return accounts, facilities
