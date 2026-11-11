"""dbt manifest parser extracting models, sources, tests, and dependency mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_platform.metadata.schemas import ColumnMetadata, ModelMetadata, SourceMetadata


class DbtManifestParser:
    """Parses dbt manifest.json artifacts into structured Python metadata objects."""

    def __init__(self, manifest_data: dict[str, Any]) -> None:
        self.manifest = manifest_data
        self.nodes = manifest_data.get("nodes", {})
        self.sources = manifest_data.get("sources", {})
        self.parent_map = manifest_data.get("parent_map", {})
        self.child_map = manifest_data.get("child_map", {})
        self._test_index: dict[str, list[dict[str, Any]]] = self._build_test_index()

    @classmethod
    def from_file(cls, path: Path) -> DbtManifestParser:
        """Load manifest parser directly from a file path."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data)

    def _build_test_index(self) -> dict[str, list[dict[str, Any]]]:
        """Index tests by target model or column for fast lookup."""
        index: dict[str, list[dict[str, Any]]] = {}
        for node_id, node in self.nodes.items():
            if node.get("resource_type") != "test":
                continue

            test_metadata = node.get("test_metadata", {})
            test_name = test_metadata.get("name") or node.get("name", "unknown_test")

            # Determine attached models from depends_on
            depends_on_nodes = node.get("depends_on", {}).get("nodes", [])
            column_name = node.get("column_name")

            for dep in depends_on_nodes:
                if dep not in index:
                    index[dep] = []
                index[dep].append(
                    {
                        "test_id": node_id,
                        "test_name": test_name,
                        "column_name": column_name,
                    }
                )
        return index

    def extract_run_metadata(self) -> dict[str, Any]:
        """Extract compilation metadata from manifest top-level metadata block."""
        return self.manifest.get("metadata", {})

    @property
    def total_tests(self) -> int:
        """Total count of test nodes in the manifest."""
        return sum(1 for node in self.nodes.values() if node.get("resource_type") == "test")

    def extract_models(self) -> dict[str, ModelMetadata]:
        """Extract all model definitions from manifest nodes."""
        models: dict[str, ModelMetadata] = {}

        for node_id, node in self.nodes.items():
            if node.get("resource_type") != "model":
                continue

            name = node.get("name", "")
            schema_name = node.get("schema", "")
            database = node.get("database", "")
            config = node.get("config", {})
            materialization = config.get("materialized", "view")
            relation_name = node.get("relation_name", f'"{schema_name}"."{name}"')
            description = node.get("description") or "Undocumented model."
            tags = node.get("tags", [])
            file_path = node.get("original_file_path")

            # Extract model layer from path (staging, intermediate, marts)
            layer = "marts"
            if "staging" in str(file_path):
                layer = "staging"
            elif "intermediate" in str(file_path):
                layer = "intermediate"

            # Extract grain from doc or meta
            meta = node.get("meta", {})
            grain = meta.get("grain")
            if not grain and description:
                # Infer grain if formatted in standard header: "Grain: ..."
                for line in description.splitlines():
                    if "Grain:" in line:
                        grain = line.split("Grain:")[-1].strip()
                        break

            # Extract dependencies
            upstream_nodes = self.parent_map.get(node_id, [])
            upstream_models = [n for n in upstream_nodes if n.startswith("model.")]
            upstream_sources = [n for n in upstream_nodes if n.startswith("source.")]

            # Associated tests
            node_tests = [
                t["test_name"]
                for t in self._test_index.get(node_id, [])
                if not t.get("column_name")
            ]

            # Columns
            columns: dict[str, ColumnMetadata] = {}
            for col_name, col_data in node.get("columns", {}).items():
                col_tests = [
                    t["test_name"]
                    for t in self._test_index.get(node_id, [])
                    if t.get("column_name") == col_name
                ]
                columns[col_name] = ColumnMetadata(
                    name=col_name,
                    data_type=col_data.get("data_type") or "TEXT",
                    description=col_data.get("description") or "Undocumented column.",
                    tests=col_tests,
                )

            models[node_id] = ModelMetadata(
                model_id=node_id,
                name=name,
                layer=layer,
                database=database,
                schema_name=schema_name,
                relation_name=relation_name,
                materialization=materialization,
                description=description,
                tags=tags,
                file_path=file_path,
                grain=grain,
                upstream_models=upstream_models,
                upstream_sources=upstream_sources,
                model_tests=node_tests,
                columns=columns,
            )

        return models

    def extract_sources(self) -> dict[str, SourceMetadata]:
        """Extract all source definitions from manifest sources."""
        sources: dict[str, SourceMetadata] = {}

        for source_id, src in self.sources.items():
            source_name = src.get("source_name", "")
            table_name = src.get("name", "")
            database = src.get("database", "")
            schema_name = src.get("schema", "")
            description = src.get("description") or "Undocumented raw source table."

            downstream_models = [
                child for child in self.child_map.get(source_id, []) if child.startswith("model.")
            ]

            src_tests = [
                t["test_name"]
                for t in self._test_index.get(source_id, [])
                if not t.get("column_name")
            ]

            columns: dict[str, ColumnMetadata] = {}
            for col_name, col_data in src.get("columns", {}).items():
                col_tests = [
                    t["test_name"]
                    for t in self._test_index.get(source_id, [])
                    if t.get("column_name") == col_name
                ]
                columns[col_name] = ColumnMetadata(
                    name=col_name,
                    data_type=col_data.get("data_type") or "TEXT",
                    description=col_data.get("description") or "Undocumented column.",
                    tests=col_tests,
                )

            sources[source_id] = SourceMetadata(
                source_id=source_id,
                source_name=source_name,
                table_name=table_name,
                database=database,
                schema_name=schema_name,
                description=description,
                columns=columns,
                downstream_models=downstream_models,
                tests=src_tests,
            )

        return sources
