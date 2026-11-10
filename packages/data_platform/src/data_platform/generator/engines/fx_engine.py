"""Deterministic FX market data engine with triangular consistency and bid/ask spreads."""

import random
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from data_platform.generator.schemas import FXRateRecord


class FXEngine:
    """Generates cross-currency exchange rate matrices with mathematical consistency."""

    # Realistic institutional anchor rates against EUR
    DEFAULT_ANCHORS: dict[str, Decimal] = {
        "EUR": Decimal("1.000000"),
        "USD": Decimal("1.085000"),
        "GBP": Decimal("0.855000"),
        "CHF": Decimal("0.945000"),
    }

    # Half-spread in basis points (5 bps = 0.0005)
    HALF_SPREAD: Decimal = Decimal("0.000500")

    def __init__(
        self,
        seed: int = 42,
        reporting_base_currency: str = "EUR",
        supported_currencies: list[str] | None = None,
    ) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.reporting_base_currency = reporting_base_currency
        self.supported_currencies = supported_currencies or ["EUR", "USD", "GBP", "CHF"]
        # Lookup table: (date, from_currency, to_currency) -> FXRateRecord
        self.rate_matrix: dict[tuple[date, str, str], FXRateRecord] = {}

    def generate_rates(self, start_date: date, end_date: date) -> list[FXRateRecord]:
        """Generate daily cross-rate records spanning the date range with seed determinism."""
        self.rate_matrix.clear()
        records: list[FXRateRecord] = []

        current_eur_anchors = dict(self.DEFAULT_ANCHORS)
        total_days = (end_date - start_date).days + 1

        for day_offset in range(total_days):
            rate_date = start_date + timedelta(days=day_offset)
            rate_timestamp = datetime.combine(rate_date, time(16, 0), tzinfo=UTC)

            # Apply daily random walk drift (±0.15% max per day) to non-EUR currencies
            for curr in self.supported_currencies:
                if curr != "EUR":
                    drift_pct = Decimal(str(round(self.rng.uniform(-0.0015, 0.0015), 6)))
                    current_eur_anchors[curr] = (
                        current_eur_anchors[curr] * (Decimal("1.000000") + drift_pct)
                    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)

            # Build full cross-currency matrix using triangular arbitrage against EUR
            for from_curr in self.supported_currencies:
                for to_curr in self.supported_currencies:
                    if from_curr == to_curr:
                        mid = Decimal("1.000000")
                        bid = Decimal("1.000000")
                        ask = Decimal("1.000000")
                    else:
                        # Triangular cross-rate formula:
                        # Mid(From -> To) = Mid(EUR -> To) / Mid(EUR -> From)
                        eur_to_from = current_eur_anchors[from_curr]
                        eur_to_to = current_eur_anchors[to_curr]
                        mid = (eur_to_to / eur_to_from).quantize(
                            Decimal("0.000001"),
                            rounding=ROUND_HALF_EVEN,
                        )
                        bid = (mid * (Decimal("1.000000") - self.HALF_SPREAD)).quantize(
                            Decimal("0.000001"),
                            rounding=ROUND_HALF_EVEN,
                        )
                        ask = (mid * (Decimal("1.000000") + self.HALF_SPREAD)).quantize(
                            Decimal("0.000001"),
                            rounding=ROUND_HALF_EVEN,
                        )

                    record = FXRateRecord(
                        rate_id=f"FX_{from_curr}_{to_curr}_{rate_date.strftime('%Y%m%d')}",
                        rate_date=rate_date,
                        from_currency=from_curr,
                        to_currency=to_curr,
                        mid_rate=mid,
                        bid_rate=bid,
                        ask_rate=ask,
                        rate_source="ECB_SYNTH",
                        rate_type="HISTORICAL_EOD",
                        rate_timestamp=rate_timestamp,
                    )
                    records.append(record)
                    self.rate_matrix[(rate_date, from_curr, to_curr)] = record

        return records

    def get_mid_rate(self, from_currency: str, to_currency: str, rate_date: date) -> Decimal:
        """Retrieve the mid-market exchange rate for a given currency pair on a specific date."""
        if from_currency == to_currency:
            return Decimal("1.000000")
        key = (rate_date, from_currency, to_currency)
        if key in self.rate_matrix:
            return self.rate_matrix[key].mid_rate
        # Fallback to anchor if not generated for that date
        eur_to_from = self.DEFAULT_ANCHORS[from_currency]
        eur_to_to = self.DEFAULT_ANCHORS[to_currency]
        return (eur_to_to / eur_to_from).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)

    def convert_amount(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: date,
    ) -> Decimal:
        """Convert a monetary amount using the mid rate on the specified date."""
        rate = self.get_mid_rate(from_currency, to_currency, rate_date)
        return (amount * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)

    def convert_to_reporting_base(
        self,
        amount: Decimal,
        from_currency: str,
        rate_date: date,
    ) -> Decimal:
        """Convert a monetary amount into the configured reporting base currency."""
        return self.convert_amount(
            amount=amount,
            from_currency=from_currency,
            to_currency=self.reporting_base_currency,
            rate_date=rate_date,
        )
