"""dbt catalog parser extracting physical database schemas, types, and column positions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_platform.metadata.schemas import ColumnMetadata, ModelMetadata, SourceMetadata


class DbtCatalogParser:
    """Parses dbt catalog.json artifacts containing physical warehouse types and stats."""

    def __init__(self, catalog_data: dict[str, Any]) -> None:
        self.catalog = catalog_data
        self.nodes = catalog_data.get("nodes", {})
        self.sources = catalog_data.get("sources", {})

    @classmethod
    def from_file(cls, path: Path) -> DbtCatalogParser:
        """Load catalog parser directly from file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    def enrich_models(self, models: dict[str, ModelMetadata]) -> None:
        """Enrich extracted models with physical database column types and ordinal positions."""
        for model_id, model in models.items():
            cat_node = self.nodes.get(model_id)
            if not cat_node:
                continue

            columns = cat_node.get("columns", {})
            for col_name, col_data in columns.items():
                physical_type = col_data.get("type", "TEXT")
                position = col_data.get("index")

                if col_name in model.columns:
                    model.columns[col_name].data_type = physical_type
                    model.columns[col_name].ordinal_position = position
                else:
                    # Column exists in database catalog but was not defined in YAML
                    model.columns[col_name] = ColumnMetadata(
                        name=col_name,
                        data_type=physical_type,
                        ordinal_position=position,
                        description="Undocumented column (discovered from warehouse catalog).",
                    )

    def enrich_sources(self, sources: dict[str, SourceMetadata]) -> None:
        """Enrich extracted sources with physical database column types and ordinal positions."""
        for source_id, src in sources.items():
            cat_source = self.sources.get(source_id)
            if not cat_source:
                continue

            columns = cat_source.get("columns", {})
            for col_name, col_data in columns.items():
                physical_type = col_data.get("type", "TEXT")
                position = col_data.get("index")

                if col_name in src.columns:
                    src.columns[col_name].data_type = physical_type
                    src.columns[col_name].ordinal_position = position
                else:
                    src.columns[col_name] = ColumnMetadata(
                        name=col_name,
                        data_type=physical_type,
                        ordinal_position=position,
                        description="Undocumented column (discovered from warehouse catalog).",
                    )
