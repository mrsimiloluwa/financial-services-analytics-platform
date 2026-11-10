"""Unit tests for CustomerEngine, AccountEngine, and FXEngine."""

from datetime import date
from decimal import Decimal

from data_platform.generator.engines.account_engine import AccountEngine
from data_platform.generator.engines.customer_engine import CustomerEngine
from data_platform.generator.engines.fx_engine import FXEngine


def test_fx_engine_triangular_and_reciprocal_consistency() -> None:
    """Verify FX rates preserve reciprocal and triangular arbitrage parity."""
    engine = FXEngine(seed=42, reporting_base_currency="EUR")
    rates = engine.generate_rates(start_date=date(2025, 1, 1), end_date=date(2025, 1, 5))
    assert len(rates) > 0

    test_date = date(2025, 1, 2)
    eur_usd = engine.get_mid_rate("EUR", "USD", test_date)
    usd_eur = engine.get_mid_rate("USD", "EUR", test_date)
    eur_gbp = engine.get_mid_rate("EUR", "GBP", test_date)
    gbp_usd = engine.get_mid_rate("GBP", "USD", test_date)

    # 1. Reciprocal consistency: EUR/USD * USD/EUR ≈ 1.0
    reciprocal_product = eur_usd * usd_eur
    assert abs(reciprocal_product - Decimal("1.000000")) < Decimal("0.000100")

    # 2. Triangular consistency: GBP/USD ≈ (EUR/USD) / (EUR/GBP)
    expected_gbp_usd = eur_usd / eur_gbp
    assert abs(gbp_usd - expected_gbp_usd) < Decimal("0.000100")

    # 3. Conversion to reporting base (EUR)
    # 100 USD converted to EUR
    converted_eur = engine.convert_to_reporting_base(Decimal("100.0000"), "USD", test_date)
    assert converted_eur > Decimal("0.0000")
    # Since EUR/USD is around 1.08, 100 USD should be around ~92 EUR
    assert Decimal("80.0000") < converted_eur < Decimal("100.0000")


def test_fx_engine_bid_ask_spreads() -> None:
    """Verify all FX rate pairs strictly satisfy bid <= mid <= ask."""
    engine = FXEngine(seed=123)
    rates = engine.generate_rates(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2))
    for r in rates:
        assert r.bid_rate <= r.mid_rate <= r.ask_rate
        if r.from_currency != r.to_currency:
            assert r.bid_rate < r.ask_rate


def test_customer_engine_distributions_and_determinism() -> None:
    """Verify customer generation is deterministic and respects segment weights."""
    c_engine_1 = CustomerEngine(seed=42)
    custs_1 = c_engine_1.generate_customers(count=100)

    c_engine_2 = CustomerEngine(seed=42)
    custs_2 = c_engine_2.generate_customers(count=100)

    # 1. Exact reproducibility for fixed seed
    assert len(custs_1) == 100
    assert [c.customer_id for c in custs_1] == [c.customer_id for c in custs_2]
    assert [c.customer_name for c in custs_1] == [c.customer_name for c in custs_2]

    # 2. Segment distributions (Retail ~50%, SME ~35%, Institutional ~15%)
    segments = [c.customer_segment for c in custs_1]
    retail_count = segments.count("RETAIL_WEALTH")
    sme_count = segments.count("COMMERCIAL_SME")
    inst_count = segments.count("INSTITUTIONAL")

    assert 40 <= retail_count <= 60
    assert 25 <= sme_count <= 45
    assert 5 <= inst_count <= 25


def test_account_engine_referential_integrity_and_overdrafts() -> None:
    """Verify account generation, multi-currency presence, and overdraft linkages."""
    c_engine = CustomerEngine(seed=42)
    customers = c_engine.generate_customers(count=50)

    a_engine = AccountEngine(seed=42)
    accounts, facilities = a_engine.generate_accounts_and_facilities(customers)

    assert len(accounts) >= 50
    assert len(facilities) > 0

    customer_ids = {c.customer_id for c in customers}
    account_ids = {a.account_id for a in accounts}

    # 1. Referential integrity: Every account belongs to a valid customer
    for acc in accounts:
        assert acc.customer_id in customer_ids
        assert acc.opening_balance >= Decimal("0.0000")
        assert acc.reserved_funds <= acc.opening_balance

    # 2. Multi-currency coverage
    currencies = {acc.currency for acc in accounts}
    assert "EUR" in currencies
    assert "USD" in currencies
    assert "GBP" in currencies

    # 3. Overdraft facilities referential integrity
    for fac in facilities:
        assert fac.account_id in account_ids
        assert fac.authorized_limit > Decimal("0.0000")
        assert fac.standard_interest_rate < fac.unauthorized_penalty_rate
        assert fac.effective_start_date < fac.effective_end_date


def test_account_engine_reproducibility() -> None:
    """Verify AccountEngine produces identical accounts given identical customers and seed."""
    c_engine = CustomerEngine(seed=77)
    customers = c_engine.generate_customers(count=20)

    accs_1, facs_1 = AccountEngine(seed=77).generate_accounts_and_facilities(customers)
    accs_2, facs_2 = AccountEngine(seed=77).generate_accounts_and_facilities(customers)

    assert [a.account_number for a in accs_1] == [a.account_number for a in accs_2]
    assert [a.opening_balance for a in accs_1] == [a.opening_balance for a in accs_2]
    assert [f.authorized_limit for f in facs_1] == [f.authorized_limit for f in facs_2]
