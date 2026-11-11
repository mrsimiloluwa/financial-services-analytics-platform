"""Unit tests for model and column data lineage engine."""

from __future__ import annotations

from data_platform.metadata.lineage import ColumnLineageAnalyzer, LineageEngine


def test_lineage_builds_model_edges() -> None:
    """Scenario 9: Directed dependency edges generated from parent_map."""
    parent_map = {
        "model.dbt.stg_orders": ["source.dbt.raw.orders"],
        "model.dbt.marts.fct_orders": ["model.dbt.stg_orders"],
    }
    engine = LineageEngine(parent_map=parent_map)
    edges = engine.build_model_edges()

    assert len(edges) == 2
    types = {e.edge_type for e in edges}
    assert "SOURCE_TO_MODEL" in types
    assert "MODEL_TO_MODEL" in types


def test_lineage_upstream_traversal() -> None:
    """Scenario 10: Upstream traversal traces all ancestor nodes."""
    parent_map = {
        "m_mart": ["m_int"],
        "m_int": ["m_stg"],
        "m_stg": ["s_raw"],
    }
    engine = LineageEngine(parent_map=parent_map)
    upstream = engine.get_upstream_nodes("m_mart")

    assert upstream == {"m_int", "m_stg", "s_raw"}


def test_lineage_downstream_traversal() -> None:
    """Scenario 11: Downstream traversal traces all descendant nodes."""
    child_map = {
        "s_raw": ["m_stg"],
        "m_stg": ["m_int"],
        "m_int": ["m_mart"],
    }
    engine = LineageEngine(child_map=child_map)
    downstream = engine.get_downstream_nodes("s_raw")

    assert downstream == {"m_stg", "m_int", "m_mart"}


def test_lineage_trace_mart_to_sources() -> None:
    """Scenario 12: Trace mart directly to its root raw sources."""
    parent_map = {
        "model.dbt_analytics.marts.fct_transactions": ["model.dbt_analytics.intermediate.int_txns"],
        "model.dbt_analytics.intermediate.int_txns": [
            "source.dbt_analytics.raw.transactions",
            "source.dbt_analytics.raw.customers",
        ],
    }
    engine = LineageEngine(parent_map=parent_map)
    sources = engine.trace_mart_to_sources("model.dbt_analytics.marts.fct_transactions")

    assert "source.dbt_analytics.raw.customers" in sources
    assert "source.dbt_analytics.raw.transactions" in sources


def test_lineage_mermaid_generation() -> None:
    """Scenario 13: Generate valid Mermaid diagram syntax."""
    parent_map = {
        "model.dbt_analytics.staging.stg_txns": ["source.dbt_analytics.raw.transactions"],
        "model.dbt_analytics.marts.fct_transactions": ["model.dbt_analytics.staging.stg_txns"],
    }
    engine = LineageEngine(parent_map=parent_map)
    mermaid = engine.generate_mermaid_diagram()

    assert "graph LR" in mermaid
    assert "source_dbt_analytics_raw_transactions" in mermaid
    assert "-->" in mermaid


def test_column_lineage_sqlglot_parsing() -> None:
    """Scenario 14: Column lineage analyzer extracts direct projections and complex expressions."""
    sql = """
    SELECT
        c.customer_id AS id,
        c.customer_name,
        COALESCE(c.city, 'Unknown') AS location,
        SUM(t.amount) OVER (PARTITION BY c.customer_id) AS total_amount
    FROM customers c
    JOIN transactions t ON c.customer_id = t.customer_id
    """
    analyzer = ColumnLineageAnalyzer(dialect="postgres")
    mapping = analyzer.analyze_sql(sql)

    assert "id" in mapping
    assert mapping["id"] == ["customer_id"]
    assert "customer_name" in mapping
    assert mapping["customer_name"] == ["customer_name"]
    assert "location" in mapping
    assert "city" in mapping["location"]
