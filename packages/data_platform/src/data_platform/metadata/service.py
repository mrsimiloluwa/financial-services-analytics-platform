"""High-level Metadata Service API for consumers, AI workflows, and governance pipelines."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import psycopg
from shared.config import get_settings
from shared.db import get_postgres_connection

from data_platform.metadata.artifacts import DbtArtifactManager
from data_platform.metadata.extractor import QUERYABLE_ALLOWLIST, MetadataExtractor
from data_platform.metadata.metrics import MetricRegistry
from data_platform.metadata.repository import MetadataRepository
from data_platform.metadata.schemas import (
    ArtifactRun,
    DataClassification,
    FinancialMetric,
    ModelMetadata,
    QueryContext,
)

logger = logging.getLogger(__name__)


class MetadataService:
    """Unified service interface for interacting with the governed financial metadata catalog."""

    def __init__(self, conn: psycopg.Connection[Any] | None = None) -> None:
        """Initialize metadata service with optional explicit PostgreSQL connection."""
        self._conn = conn

    def _get_repo(self, conn: psycopg.Connection[Any]) -> MetadataRepository:
        return MetadataRepository(conn)

    def publish_and_load(
        self,
        target_dir: Path | str,
        artifacts_root: Path | str = "artifacts/dbt",
        environment: str = "dev",
    ) -> ArtifactRun:
        """Extract metadata from target_dir, version-publish artifacts, and persist to database."""
        target_path = Path(target_dir)
        manager = DbtArtifactManager(
            dbt_target_dir=target_path,
            artifacts_root=Path(artifacts_root),
        )

        # 1. Publish versioned artifacts
        artifact_run = manager.publish_artifacts(environment=environment)
        logger.info("Published versioned artifacts to %s", artifact_run.artifact_path)

        # 2. Extract snapshot
        extractor = MetadataExtractor(target_dir=target_path, environment=environment)
        snapshot = extractor.extract()
        snapshot.artifact_run = artifact_run

        # 3. Persist to PostgreSQL
        if self._conn:
            repo = self._get_repo(self._conn)
            repo.save_snapshot(snapshot)
        else:
            with get_postgres_connection() as conn:
                repo = self._get_repo(conn)
                repo.save_snapshot(snapshot)

        return snapshot.artifact_run

    def _get_standalone_models(self) -> dict[str, ModelMetadata]:
        """Extract model metadata directly from dbt artifacts when running without PostgreSQL."""
        search_paths = [
            Path("packages/data_platform/dbt_analytics/target"),
            Path(__file__).resolve().parents[3] / "dbt_analytics" / "target",
            Path.cwd() / "packages" / "data_platform" / "dbt_analytics" / "target",
        ]
        target_dir = None
        for p in search_paths:
            if p.exists() and (p / "manifest.json").exists():
                target_dir = p
                break
        if not target_dir:
            return {}
        try:
            snapshot = MetadataExtractor(target_dir=target_dir).extract()
            return {m.name: m for m in snapshot.models.values()}
        except Exception as exc:
            logger.warning("Could not extract standalone models from %s: %s", target_dir, exc)
            return {}

    def get_model(self, model_name: str) -> ModelMetadata | None:
        """Retrieve model metadata by name."""
        if self._conn:
            return self._get_repo(self._conn).get_model(model_name)
        cfg = get_settings()
        if cfg.is_duckdb:
            return self._get_standalone_models().get(model_name)
        try:
            with get_postgres_connection() as conn:
                return self._get_repo(conn).get_model(model_name)
        except Exception as exc:
            logger.debug(
                "PostgreSQL get_model failed, falling back to standalone dbt artifacts: %s", exc
            )
            return self._get_standalone_models().get(model_name)

    def list_queryable_models(self) -> list[ModelMetadata]:
        """List all models permitted for AI reasoning and direct analytical query."""
        if self._conn:
            return self._get_repo(self._conn).list_queryable_models()
        cfg = get_settings()
        if cfg.is_duckdb:
            models = self._get_standalone_models()
            return [m for m in models.values() if m.is_queryable]
        try:
            with get_postgres_connection() as conn:
                return self._get_repo(conn).list_queryable_models()
        except Exception as exc:
            logger.debug(
                "PostgreSQL list_queryable_models failed, falling back to standalone: %s", exc
            )
            models = self._get_standalone_models()
            return [m for m in models.values() if m.is_queryable]

    def list_metrics(self) -> list[FinancialMetric]:
        """List all governed financial metrics."""
        if self._conn:
            return self._get_repo(self._conn).list_metrics()
        cfg = get_settings()
        if cfg.is_duckdb:
            return MetricRegistry.from_yaml().list_all()
        try:
            with get_postgres_connection() as conn:
                return self._get_repo(conn).list_metrics()
        except Exception as exc:
            logger.debug("PostgreSQL list_metrics failed, falling back to MetricRegistry: %s", exc)
            return MetricRegistry.from_yaml().list_all()

    def get_metric(self, metric_id: str) -> FinancialMetric | None:
        """Retrieve a specific financial metric by ID."""
        if self._conn:
            return self._get_repo(self._conn).get_metric(metric_id)
        cfg = get_settings()
        if cfg.is_duckdb:
            return MetricRegistry.from_yaml().get(metric_id)
        try:
            with get_postgres_connection() as conn:
                return self._get_repo(conn).get_metric(metric_id)
        except Exception as exc:
            logger.debug("PostgreSQL get_metric failed, falling back to MetricRegistry: %s", exc)
            return MetricRegistry.from_yaml().get(metric_id)

    def build_ai_query_context(self, model_name: str) -> QueryContext:
        """Build an authorized context package for AI reasoning and SQL generation."""
        if model_name not in QUERYABLE_ALLOWLIST:
            raise PermissionError(
                f"Model '{model_name}' is not in the governed queryable allowlist. "
                f"AI workflows are restricted to dimensional finance marts and core dimensions: "
                f"{sorted(QUERYABLE_ALLOWLIST)}."
            )

        model = self.get_model(model_name)
        if not model:
            raise ValueError(f"Model '{model_name}' does not exist in the metadata catalog.")

        # Gather columns
        columns_desc: dict[str, str] = {}
        date_fields: list[str] = []
        currency_fields: list[str] = []

        for col_name, col in model.columns.items():
            if col.classification == DataClassification.RESTRICTED:
                continue  # Never expose restricted columns
            columns_desc[col_name] = f"{col.data_type}: {col.description}"
            if "date" in col_name.lower() or "month" in col_name.lower():
                date_fields.append(col_name)
            if "currency" in col_name.lower():
                currency_fields.append(col_name)

        # Gather relevant metrics
        all_metrics = self.list_metrics()
        model_metrics = [m for m in all_metrics if m.source_model == model_name]
        metric_names = [f"{m.metric_name} ({m.metric_id}): {m.formula}" for m in model_metrics]

        # Gather example questions from metrics
        example_questions: list[str] = []
        for m in model_metrics:
            example_questions.extend(m.example_business_questions)

        # Standard safe joins
        safe_joins: list[dict[str, str]] = []
        if "customer_id" in model.columns and model_name != "dim_customers":
            safe_joins.append(
                {
                    "dimension": "dim_customers",
                    "join_key": "customer_id",
                    "type": "LEFT JOIN",
                    "purpose": "Enrich with customer segmentation and master attributes",
                }
            )
        if "account_id" in model.columns and model_name != "dim_accounts":
            safe_joins.append(
                {
                    "dimension": "dim_accounts",
                    "join_key": "account_id",
                    "type": "LEFT JOIN",
                    "purpose": "Enrich with account details and subledger balance",
                }
            )

        # Governed restrictions
        restrictions = [
            "READ-ONLY ACCESS: Never generate DDL (CREATE, DROP, ALTER) or DML (INSERT, UPDATE, DELETE).",
            "GOVERNED METRICS: Always use official formulas; do not invent ad-hoc metric calculations.",
            "MULTI-CURRENCY SAFETY: Never sum native currency columns across differing currencies without GROUP BY currency.",
            "EUR REPORTING: For cross-currency aggregation, use explicit _eur columns (e.g. transaction_amount_eur, net_recognized_revenue_eur).",
            "MAX ROWS: Always include LIMIT 1000 unless performing aggregated group queries.",
        ]

        return QueryContext(
            model_name=model.name,
            description=model.description,
            business_purpose=f"Dimensional analytics mart for {model.name}",
            grain=model.grain or "Undocumented grain",
            classification=model.classification,
            columns=columns_desc,
            available_metrics=metric_names,
            date_fields=date_fields,
            currency_fields=currency_fields,
            safe_joins=safe_joins,
            example_questions=example_questions[:5],
            restrictions=restrictions,
        )
