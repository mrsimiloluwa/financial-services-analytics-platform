"""Unit tests for physical dbt catalog parser."""

from __future__ import annotations

from data_platform.metadata.dbt_catalog import DbtCatalogParser
from data_platform.metadata.schemas import ColumnMetadata, ModelMetadata


def test_catalog_parser_enriches_column_types() -> None:
    """Scenario 4: Catalog parser updates columns with physical warehouse types."""
    catalog_data = {
        "nodes": {
            "model.dbt_analytics.dim_customers": {
                "columns": {
                    "customer_id": {"type": "character varying(64)", "index": 1},
                    "onboarding_date": {"type": "date", "index": 2},
                }
            }
        }
    }

    models = {
        "model.dbt_analytics.dim_customers": ModelMetadata(
            model_id="model.dbt_analytics.dim_customers",
            name="dim_customers",
            layer="marts",
            database="analytics_platform",
            schema_name="analytics",
            relation_name="analytics.dim_customers",
            materialization="table",
            columns={
                "customer_id": ColumnMetadata(name="customer_id", data_type="TEXT"),
                "onboarding_date": ColumnMetadata(name="onboarding_date", data_type="TEXT"),
            },
        )
    }

    parser = DbtCatalogParser(catalog_data)
    parser.enrich_models(models)

    model = models["model.dbt_analytics.dim_customers"]
    assert model.columns["customer_id"].data_type == "character varying(64)"
    assert model.columns["customer_id"].ordinal_position == 1
    assert model.columns["onboarding_date"].data_type == "date"
    assert model.columns["onboarding_date"].ordinal_position == 2
