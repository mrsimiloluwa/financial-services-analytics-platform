"""Unit tests for DuckDB analytical capabilities and financial decimal precision."""

from decimal import Decimal

from shared.db import get_duckdb_connection


def test_duckdb_in_memory_connection() -> None:
    """Verify DuckDB can open an in-memory database and execute basic queries."""
    conn = get_duckdb_connection(":memory:")
    result = conn.execute("SELECT 42 AS answer").fetchone()
    assert result is not None
    assert result[0] == 42
    conn.close()


def test_duckdb_financial_precision() -> None:
    """Verify monetary calculations avoid IEEE-754 floating point imprecision."""
    conn = get_duckdb_connection(":memory:")
    # Financial scenario: 3 transactions of 0.10 currency units
    # In IEEE-754 floating point: 0.1 + 0.1 + 0.1 == 0.30000000000000004
    # With DECIMAL(18, 4), it must strictly equal 0.3000
    query = """
    CREATE TABLE mock_transactions (
        txn_id VARCHAR,
        fee_amount DECIMAL(18, 4)
    );
    INSERT INTO mock_transactions VALUES
        ('T1', 0.1000),
        ('T2', 0.1000),
        ('T3', 0.1000);
    SELECT SUM(fee_amount) AS total_fee FROM mock_transactions;
    """
    result = conn.execute(query).fetchall()
    total_fee = result[-1][0]
    assert total_fee == Decimal("0.3000")
    conn.close()
