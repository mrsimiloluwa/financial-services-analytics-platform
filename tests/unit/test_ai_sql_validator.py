"""Unit tests for SQLGlot AST security validator."""

from __future__ import annotations

import pytest
from ai_services.security.sql_validator import SQLGlotASTValidator


@pytest.fixture
def validator() -> SQLGlotASTValidator:
    return SQLGlotASTValidator()


def test_valid_select_query(validator: SQLGlotASTValidator):
    sql = "SELECT customer_id, net_recognized_revenue_eur FROM analytics.fct_customer_revenue LIMIT 10;"
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is True
    assert "analytics.fct_customer_revenue" in result.tables_accessed
    assert "LIMIT 10" in result.sanitized_sql


def test_schema_normalization(validator: SQLGlotASTValidator):
    # Query without explicit schema prefix should be normalized to analytics.
    sql = "SELECT customer_id FROM fct_customer_revenue;"
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is True
    assert "analytics.fct_customer_revenue" in result.tables_accessed
    assert "analytics.fct_customer_revenue" in result.sanitized_sql.lower()


def test_reject_multiple_statements(validator: SQLGlotASTValidator):
    sql = "SELECT * FROM analytics.fct_customer_revenue; DROP TABLE analytics.fct_customer_revenue;"
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "Multiple statements" in result.error_message


def test_reject_dml_operations(validator: SQLGlotASTValidator):
    queries = [
        "DELETE FROM analytics.fct_customer_revenue WHERE 1=1;",
        "UPDATE analytics.fct_customer_revenue SET net_recognized_revenue_eur = 0;",
        "INSERT INTO analytics.fct_customer_revenue (customer_id) VALUES ('123');",
        "TRUNCATE TABLE analytics.fct_customer_revenue;",
        "MERGE INTO analytics.fct_customer_revenue USING analytics.dim_customers ON 1=1 WHEN MATCHED THEN DELETE;",
    ]
    for q in queries:
        result = validator.validate_and_sanitize(q)
        assert result.is_valid is False
        assert (
            "Only read-only SELECT" in result.error_message or "Prohibited" in result.error_message
        )


def test_reject_ddl_operations(validator: SQLGlotASTValidator):
    queries = [
        "DROP TABLE analytics.fct_customer_revenue;",
        "CREATE TABLE analytics.hacked (id int);",
        "ALTER TABLE analytics.fct_customer_revenue DROP COLUMN customer_id;",
    ]
    for q in queries:
        result = validator.validate_and_sanitize(q)
        assert result.is_valid is False
        assert "Only read-only SELECT" in result.error_message


def test_reject_select_into(validator: SQLGlotASTValidator):
    sql = "SELECT * INTO hacked_table FROM analytics.fct_customer_revenue;"
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "Prohibited" in result.error_message


def test_reject_dangerous_functions(validator: SQLGlotASTValidator):
    queries = [
        "SELECT pg_sleep(5);",
        "SELECT pg_read_file('/etc/passwd');",
        "SELECT query_to_xml('SELECT 1', true, false, '');",
        "SELECT dblink('host=evil', 'SELECT 1');",
    ]
    for q in queries:
        result = validator.validate_and_sanitize(q)
        assert result.is_valid is False
        assert "prohibited function" in result.error_message.lower()


def test_valid_cte_usage(validator: SQLGlotASTValidator):
    sql = """
        WITH customer_summary AS (
            SELECT customer_id, SUM(net_recognized_revenue_eur) AS total_revenue
            FROM analytics.fct_customer_revenue
            GROUP BY customer_id
        )
        SELECT c.customer_name, s.total_revenue
        FROM customer_summary s
        JOIN analytics.dim_customers c ON s.customer_id = c.customer_id
        LIMIT 5;
    """
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is True
    assert "analytics.fct_customer_revenue" in result.tables_accessed
    assert "analytics.dim_customers" in result.tables_accessed


def test_reject_cte_referencing_raw_schema(validator: SQLGlotASTValidator):
    sql = """
        WITH leaked_customers AS (
            SELECT * FROM raw.customers
        )
        SELECT * FROM leaked_customers;
    """
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "Access denied to schema 'raw'" in result.error_message


def test_reject_schema_qualified_cte(validator: SQLGlotASTValidator):
    sql = """
        WITH my_cte AS (
            SELECT * FROM analytics.fct_transactions
        )
        SELECT * FROM analytics.my_cte;
    """
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "cannot be schema-qualified" in result.error_message


def test_valid_union_queries(validator: SQLGlotASTValidator):
    sql = """
        SELECT customer_id FROM analytics.fct_transactions
        UNION
        SELECT customer_id FROM analytics.dim_customers;
    """
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is True
    assert "LIMIT 1000" in result.sanitized_sql


def test_reject_union_with_disallowed_schema(validator: SQLGlotASTValidator):
    sql = """
        SELECT customer_id FROM analytics.fct_transactions
        UNION ALL
        SELECT customer_id FROM raw.customers;
    """
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "Access denied to schema 'raw'" in result.error_message


def test_reject_nested_subquery_disallowed_schema(validator: SQLGlotASTValidator):
    sql = """
        SELECT * FROM analytics.fct_transactions
        WHERE customer_id IN (SELECT customer_id FROM raw.customers);
    """
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "Access denied to schema 'raw'" in result.error_message


def test_reject_unauthorized_schemas(validator: SQLGlotASTValidator):
    queries = [
        "SELECT * FROM raw.customers;",
        "SELECT * FROM staging.stg_customers;",
        "SELECT * FROM metadata.model_metadata;",
        "SELECT * FROM information_schema.tables;",
        "SELECT * FROM pg_catalog.pg_tables;",
    ]
    for q in queries:
        result = validator.validate_and_sanitize(q)
        assert result.is_valid is False
        assert "Access denied" in result.error_message


def test_reject_non_allowlist_tables(validator: SQLGlotASTValidator):
    sql = "SELECT * FROM analytics.stg_transactions;"
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "not in the governed queryable allowlist" in result.error_message


def test_reject_restricted_column_patterns(validator: SQLGlotASTValidator):
    sql = "SELECT customer_id, user_password_hash FROM analytics.fct_customer_revenue;"
    result = validator.validate_and_sanitize(sql)
    assert result.is_valid is False
    assert "RESTRICTED" in result.error_message


def test_limit_injection_and_clamping(validator: SQLGlotASTValidator):
    # Missing limit should have LIMIT 1000 injected
    sql_no_limit = "SELECT customer_id FROM analytics.fct_customer_revenue;"
    res1 = validator.validate_and_sanitize(sql_no_limit)
    assert res1.is_valid is True
    assert "LIMIT 1000" in res1.sanitized_sql

    # Limit exceeding 1000 should be clamped to 1000
    sql_high_limit = "SELECT customer_id FROM analytics.fct_customer_revenue LIMIT 50000;"
    res2 = validator.validate_and_sanitize(sql_high_limit)
    assert res2.is_valid is True
    assert "LIMIT 1000" in res2.sanitized_sql
    assert "50000" not in res2.sanitized_sql


def test_smaller_user_limit_is_preserved_not_widened(validator: SQLGlotASTValidator):
    """A user LIMIT below the cap must stay as-is (previously every LIMIT became 1000)."""
    res = validator.validate_and_sanitize(
        "SELECT customer_id FROM analytics.fct_customer_revenue LIMIT 10;"
    )
    assert res.is_valid
    assert res.sanitized_sql.rstrip(";").endswith("LIMIT 10")
    assert "LIMIT 1000" not in res.sanitized_sql
