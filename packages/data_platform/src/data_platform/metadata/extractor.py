"""Unified metadata extraction orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from data_platform.metadata.artifacts import DbtArtifactManager
from data_platform.metadata.classifications import ClassificationEngine
from data_platform.metadata.dbt_catalog import DbtCatalogParser
from data_platform.metadata.dbt_manifest import DbtManifestParser
from data_platform.metadata.lineage import ColumnLineageAnalyzer, LineageEngine
from data_platform.metadata.metrics import MetricRegistry, MetricValidator
from data_platform.metadata.schemas import (
    ArtifactRun,
    FinancialMetric,
    LineageEdge,
    ModelMetadata,
    SourceMetadata,
)

logger = logging.getLogger(__name__)

QUERYABLE_ALLOWLIST: set[str] = {
    "dim_customers",
    "dim_accounts",
    "dim_gl_accounts",
    "dim_date",
    "fct_transactions",
    "fct_fee_assessments",
    "fct_fee_collections",
    "fct_customer_revenue",
    "fct_ledger_entries",
}


@dataclass
class MetadataSnapshot:
    """Complete bundle of extracted, validated, and classified metadata."""

    artifact_run: ArtifactRun
    models: dict[str, ModelMetadata] = field(default_factory=dict)
    sources: dict[str, SourceMetadata] = field(default_factory=dict)
    metrics: dict[str, FinancialMetric] = field(default_factory=dict)
    edges: list[LineageEdge] = field(default_factory=list)
    lineage_engine: LineageEngine | None = None
    validation_errors: dict[str, list[str]] = field(default_factory=dict)


class MetadataExtractor:
    """Extracts, cross-references, validates, and classifies metadata from dbt artifacts."""

    def __init__(
        self,
        target_dir: Path | str,
        environment: str = "dev",
        metrics_path: Path | str | None = None,
    ) -> None:
        """Initialize extractor with target directory containing dbt artifacts."""
        self.target_dir = Path(target_dir)
        self.environment = environment
        self.metrics_path = metrics_path
        self.artifact_manager = DbtArtifactManager(self.target_dir)

    def extract(self) -> MetadataSnapshot:
        """Run the end-to-end metadata extraction and validation pipeline."""
        logger.info("Starting metadata extraction from %s (%s)", self.target_dir, self.environment)

        # 1. Load artifacts
        manifest_data = self.artifact_manager.load_manifest()
        catalog_data = self.artifact_manager.load_catalog()

        # 2. Parse manifest
        manifest_parser = DbtManifestParser(manifest_data)
        manifest_meta = manifest_parser.extract_run_metadata()
        models = manifest_parser.extract_models()
        sources = manifest_parser.extract_sources()

        # 3. Enrich with physical catalog
        catalog_parser = DbtCatalogParser(catalog_data)
        catalog_parser.enrich_models(models)
        catalog_parser.enrich_sources(sources)

        # 4. Classify data sensitivity
        classifier = ClassificationEngine()
        classifier.classify_models(models)
        classifier.classify_sources(sources)

        # 5. Determine queryable allowlist
        for model in models.values():
            if model.name in QUERYABLE_ALLOWLIST:
                model.is_queryable = True
            else:
                model.is_queryable = False

        # 6. Build Lineage Graph
        lineage_engine = LineageEngine(
            parent_map=manifest_parser.parent_map,
            child_map=manifest_parser.child_map,
        )
        edges = lineage_engine.build_model_edges()

        # 7. Conservative Column-Level Lineage Analysis
        col_analyzer = ColumnLineageAnalyzer()
        for node_id, model in models.items():
            node_data = manifest_data.get("nodes", {}).get(node_id, {})
            sql_code = node_data.get("compiled_code") or node_data.get("raw_code", "")
            if sql_code and "select" in sql_code.lower():
                col_lineage = col_analyzer.analyze_sql(sql_code)
                for col_name, upstream_cols in col_lineage.items():
                    if col_name in model.columns:
                        model.columns[col_name].upstream_columns = upstream_cols

        # 8. Load & Validate Governed Financial Metrics
        if self.metrics_path:
            metric_registry = MetricRegistry.from_yaml(self.metrics_path)
        else:
            metric_registry = MetricRegistry.from_yaml()

        # Index models by simple name for metric validator
        models_by_name = {m.name: m for m in models.values()}
        validator = MetricValidator(models_by_name)
        validation_errors = validator.validate_all(metric_registry)

        if validation_errors:
            logger.warning("Financial metric validation errors found: %s", validation_errors)

        metrics = {m.metric_id: m for m in metric_registry.list_all()}

        # 9. Formulate ArtifactRun record
        first_model = next(iter(models.values()), None)
        default_db = (
            "analytics_platform_test" if self.environment == "test" else "analytics_platform"
        )
        database_name = first_model.database if first_model else default_db
        schema_name = first_model.schema_name if first_model else "analytics"

        artifact_run = ArtifactRun(
            run_id=f"run_{int(datetime.now(UTC).timestamp())}",
            environment=self.environment,
            created_at=manifest_meta.get("generated_at", datetime.now(UTC)),
            dbt_version=manifest_meta.get("dbt_version", "unknown"),
            adapter_type=manifest_meta.get("adapter_type", "postgres"),
            target_name=manifest_meta.get("target_name", self.environment),
            database_name=database_name,
            schema_name=schema_name,
            total_models=len(models),
            total_sources=len(sources),
            total_tests=manifest_parser.total_tests,
            build_status="SUCCESS",
            artifact_path=str(self.target_dir),
            is_latest=True,
        )

        return MetadataSnapshot(
            artifact_run=artifact_run,
            models=models,
            sources=sources,
            metrics=metrics,
            edges=edges,
            lineage_engine=lineage_engine,
            validation_errors=validation_errors,
        )
