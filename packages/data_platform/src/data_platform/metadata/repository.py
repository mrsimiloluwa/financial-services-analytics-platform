"""PostgreSQL repository for metadata persistence and query operations."""

from __future__ import annotations

import json
import logging
from typing import Any

import psycopg
from psycopg.rows import dict_row

from data_platform.metadata.extractor import MetadataSnapshot
from data_platform.metadata.schemas import (
    ArtifactRun,
    ColumnMetadata,
    DataClassification,
    FinancialMetric,
    ModelMetadata,
)

logger = logging.getLogger(__name__)


class MetadataRepository:
    """Manages transactional persistence and retrieval of metadata records in PostgreSQL."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        """Initialize repository with an active PostgreSQL connection."""
        self.conn = conn

    def save_snapshot(self, snapshot: MetadataSnapshot) -> None:
        """Transactionally persist a full metadata snapshot into the metadata schema."""
        run = snapshot.artifact_run
        snapshot_id = run.run_id

        try:
            with self.conn.cursor() as cur:
                # 1. Update previous latest artifact runs for this environment only if this run is latest
                if run.is_latest:
                    cur.execute(
                        """
                        UPDATE metadata.artifact_runs
                        SET is_latest = FALSE
                        WHERE environment = %s;
                        """,
                        (run.environment,),
                    )

                # 2. Insert ArtifactRun
                cur.execute(
                    """
                    INSERT INTO metadata.artifact_runs (
                        run_id, environment, created_at, dbt_version, adapter_type,
                        target_name, database_name, schema_name, total_models,
                        total_sources, total_tests, build_status, artifact_path, is_latest
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        is_latest = EXCLUDED.is_latest,
                        total_models = EXCLUDED.total_models,
                        total_sources = EXCLUDED.total_sources,
                        total_tests = EXCLUDED.total_tests;
                    """,
                    (
                        run.run_id,
                        run.environment,
                        run.created_at,
                        run.dbt_version,
                        run.adapter_type,
                        run.target_name,
                        run.database_name,
                        run.schema_name,
                        run.total_models,
                        run.total_sources,
                        run.total_tests,
                        run.build_status,
                        run.artifact_path,
                        run.is_latest,
                    ),
                )

                # 3. Models and Columns
                for model in snapshot.models.values():
                    cur.execute(
                        """
                        INSERT INTO metadata.model_catalog (
                            model_id, model_name, layer, database_name, schema_name,
                            relation_name, materialization, description, tags,
                            file_path, grain, classification, is_queryable,
                            upstream_models, upstream_sources, model_tests, snapshot_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (model_id) DO UPDATE SET
                            description = EXCLUDED.description,
                            tags = EXCLUDED.tags,
                            grain = EXCLUDED.grain,
                            classification = EXCLUDED.classification,
                            is_queryable = EXCLUDED.is_queryable,
                            upstream_models = EXCLUDED.upstream_models,
                            upstream_sources = EXCLUDED.upstream_sources,
                            model_tests = EXCLUDED.model_tests,
                            snapshot_id = EXCLUDED.snapshot_id,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            model.model_id,
                            model.name,
                            model.layer,
                            model.database,
                            model.schema_name,
                            model.relation_name,
                            model.materialization,
                            model.description,
                            json.dumps(model.tags),
                            model.file_path,
                            model.grain,
                            model.classification.value,
                            model.is_queryable,
                            json.dumps(model.upstream_models),
                            json.dumps(model.upstream_sources),
                            json.dumps(model.model_tests),
                            snapshot_id,
                        ),
                    )

                    for col_name, col in model.columns.items():
                        column_id = f"{model.model_id}.{col_name}"
                        cur.execute(
                            """
                            INSERT INTO metadata.column_catalog (
                                column_id, model_id, column_name, ordinal_position,
                                data_type, description, classification, is_nullable,
                                tests, upstream_columns, snapshot_id
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (column_id) DO UPDATE SET
                                ordinal_position = EXCLUDED.ordinal_position,
                                data_type = EXCLUDED.data_type,
                                description = EXCLUDED.description,
                                classification = EXCLUDED.classification,
                                is_nullable = EXCLUDED.is_nullable,
                                tests = EXCLUDED.tests,
                                upstream_columns = EXCLUDED.upstream_columns,
                                snapshot_id = EXCLUDED.snapshot_id,
                                updated_at = CURRENT_TIMESTAMP;
                            """,
                            (
                                column_id,
                                model.model_id,
                                col.name,
                                col.ordinal_position,
                                col.data_type,
                                col.description,
                                col.classification.value,
                                col.is_nullable,
                                json.dumps(col.tests),
                                json.dumps(col.upstream_columns),
                                snapshot_id,
                            ),
                        )

                # 4. Sources
                for src in snapshot.sources.values():
                    cur.execute(
                        """
                        INSERT INTO metadata.source_catalog (
                            source_id, source_name, table_name, database_name,
                            schema_name, description, column_count, classification,
                            downstream_models, tests, snapshot_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_id) DO UPDATE SET
                            description = EXCLUDED.description,
                            column_count = EXCLUDED.column_count,
                            classification = EXCLUDED.classification,
                            downstream_models = EXCLUDED.downstream_models,
                            tests = EXCLUDED.tests,
                            snapshot_id = EXCLUDED.snapshot_id,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            src.source_id,
                            src.source_name,
                            src.table_name,
                            src.database,
                            src.schema_name,
                            src.description,
                            len(src.columns),
                            src.classification.value,
                            json.dumps(src.downstream_models),
                            json.dumps(src.tests),
                            snapshot_id,
                        ),
                    )

                # 5. Financial Metrics
                for metric in snapshot.metrics.values():
                    cur.execute(
                        """
                        INSERT INTO metadata.metric_catalog (
                            metric_id, metric_name, business_definition, formula,
                            source_model, relevant_columns, grain, aggregation_behavior,
                            native_currency_treatment, reporting_currency_conversion,
                            date_field, applicable_filters, data_quality_requirements,
                            classification, example_business_questions, known_limitations,
                            snapshot_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (metric_id) DO UPDATE SET
                            metric_name = EXCLUDED.metric_name,
                            business_definition = EXCLUDED.business_definition,
                            formula = EXCLUDED.formula,
                            source_model = EXCLUDED.source_model,
                            relevant_columns = EXCLUDED.relevant_columns,
                            grain = EXCLUDED.grain,
                            aggregation_behavior = EXCLUDED.aggregation_behavior,
                            native_currency_treatment = EXCLUDED.native_currency_treatment,
                            reporting_currency_conversion = EXCLUDED.reporting_currency_conversion,
                            date_field = EXCLUDED.date_field,
                            applicable_filters = EXCLUDED.applicable_filters,
                            data_quality_requirements = EXCLUDED.data_quality_requirements,
                            classification = EXCLUDED.classification,
                            example_business_questions = EXCLUDED.example_business_questions,
                            known_limitations = EXCLUDED.known_limitations,
                            snapshot_id = EXCLUDED.snapshot_id,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            metric.metric_id,
                            metric.metric_name,
                            metric.business_definition,
                            metric.formula,
                            metric.source_model,
                            json.dumps(metric.relevant_columns),
                            metric.grain,
                            metric.aggregation_behavior,
                            metric.native_currency_treatment,
                            metric.reporting_currency_conversion,
                            metric.date_field,
                            metric.applicable_filters,
                            metric.data_quality_requirements,
                            metric.classification.value,
                            json.dumps(metric.example_business_questions),
                            metric.known_limitations,
                            snapshot_id,
                        ),
                    )

                # 6. Lineage Edges
                for edge in snapshot.edges:
                    edge_id = f"{edge.source_id}->{edge.target_id}"
                    cur.execute(
                        """
                        INSERT INTO metadata.lineage_edges (
                            edge_id, source_id, target_id, edge_type, details, snapshot_id
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (edge_id) DO UPDATE SET
                            edge_type = EXCLUDED.edge_type,
                            details = EXCLUDED.details,
                            snapshot_id = EXCLUDED.snapshot_id;
                        """,
                        (
                            edge_id,
                            edge.source_id,
                            edge.target_id,
                            edge.edge_type,
                            json.dumps(edge.details),
                            snapshot_id,
                        ),
                    )

            self.conn.commit()
            logger.info("Successfully persisted metadata snapshot '%s' to database", snapshot_id)
        except Exception:
            self.conn.rollback()
            logger.exception("Failed to persist metadata snapshot; transaction rolled back")
            raise

    def get_latest_artifact_run(self, environment: str = "dev") -> ArtifactRun | None:
        """Retrieve the latest registered artifact run for an environment."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT run_id, environment, created_at, dbt_version, adapter_type,
                       target_name, database_name, schema_name, total_models,
                       total_sources, total_tests, build_status, artifact_path, is_latest
                FROM metadata.artifact_runs
                WHERE environment = %s AND is_latest = TRUE
                LIMIT 1;
                """,
                (environment,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return ArtifactRun(**row)

    def list_queryable_models(self) -> list[ModelMetadata]:
        """Return all models marked as queryable for AI and business consumers."""
        models: list[ModelMetadata] = []
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT model_id, model_name as name, layer, database_name as database,
                       schema_name, relation_name, materialization, description,
                       tags, file_path, grain, classification, is_queryable,
                       upstream_models, upstream_sources, model_tests
                FROM metadata.model_catalog
                WHERE is_queryable = TRUE
                ORDER BY model_name;
                """
            )
            for row in cur.fetchall():
                row["tags"] = (
                    row["tags"] if isinstance(row["tags"], list) else json.loads(row["tags"])
                )
                row["upstream_models"] = (
                    row["upstream_models"]
                    if isinstance(row["upstream_models"], list)
                    else json.loads(row["upstream_models"])
                )
                row["upstream_sources"] = (
                    row["upstream_sources"]
                    if isinstance(row["upstream_sources"], list)
                    else json.loads(row["upstream_sources"])
                )
                row["model_tests"] = (
                    row["model_tests"]
                    if isinstance(row["model_tests"], list)
                    else json.loads(row["model_tests"])
                )
                row["classification"] = DataClassification(row["classification"])
                model = ModelMetadata(**row)
                model.columns = self._get_columns_for_model(cur, model.model_id)
                models.append(model)
        return models

    def get_model(self, model_name: str) -> ModelMetadata | None:
        """Retrieve full metadata for a model by name."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT model_id, model_name as name, layer, database_name as database,
                       schema_name, relation_name, materialization, description,
                       tags, file_path, grain, classification, is_queryable,
                       upstream_models, upstream_sources, model_tests
                FROM metadata.model_catalog
                WHERE model_name = %s
                LIMIT 1;
                """,
                (model_name,),
            )
            row = cur.fetchone()
            if not row:
                return None
            row["tags"] = row["tags"] if isinstance(row["tags"], list) else json.loads(row["tags"])
            row["upstream_models"] = (
                row["upstream_models"]
                if isinstance(row["upstream_models"], list)
                else json.loads(row["upstream_models"])
            )
            row["upstream_sources"] = (
                row["upstream_sources"]
                if isinstance(row["upstream_sources"], list)
                else json.loads(row["upstream_sources"])
            )
            row["model_tests"] = (
                row["model_tests"]
                if isinstance(row["model_tests"], list)
                else json.loads(row["model_tests"])
            )
            row["classification"] = DataClassification(row["classification"])
            model = ModelMetadata(**row)
            model.columns = self._get_columns_for_model(cur, model.model_id)
            return model

    def _get_columns_for_model(
        self, cur: psycopg.Cursor[Any], model_id: str
    ) -> dict[str, ColumnMetadata]:
        """Fetch all column metadata records for a model."""
        cur.execute(
            """
            SELECT column_name as name, data_type, ordinal_position, description,
                   classification, is_nullable, tests, upstream_columns
            FROM metadata.column_catalog
            WHERE model_id = %s
            ORDER BY ordinal_position NULLS LAST, column_name;
            """,
            (model_id,),
        )
        columns: dict[str, ColumnMetadata] = {}
        for row in cur.fetchall():
            row["tests"] = (
                row["tests"] if isinstance(row["tests"], list) else json.loads(row["tests"])
            )
            row["upstream_columns"] = (
                row["upstream_columns"]
                if isinstance(row["upstream_columns"], list)
                else json.loads(row["upstream_columns"])
            )
            row["classification"] = DataClassification(row["classification"])
            columns[row["name"]] = ColumnMetadata(**row)
        return columns

    def list_metrics(self) -> list[FinancialMetric]:
        """Retrieve all governed financial metrics from the database catalog."""
        metrics: list[FinancialMetric] = []
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT metric_id, metric_name, business_definition, formula,
                       source_model, relevant_columns, grain, aggregation_behavior,
                       native_currency_treatment, reporting_currency_conversion,
                       date_field, applicable_filters, data_quality_requirements,
                       classification, example_business_questions, known_limitations
                FROM metadata.metric_catalog
                ORDER BY metric_id;
                """
            )
            for row in cur.fetchall():
                row["relevant_columns"] = (
                    row["relevant_columns"]
                    if isinstance(row["relevant_columns"], list)
                    else json.loads(row["relevant_columns"])
                )
                row["example_business_questions"] = (
                    row["example_business_questions"]
                    if isinstance(row["example_business_questions"], list)
                    else json.loads(row["example_business_questions"])
                )
                row["classification"] = DataClassification(row["classification"])
                metrics.append(FinancialMetric(**row))
        return metrics

    def get_metric(self, metric_id: str) -> FinancialMetric | None:
        """Retrieve a specific financial metric by metric_id."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT metric_id, metric_name, business_definition, formula,
                       source_model, relevant_columns, grain, aggregation_behavior,
                       native_currency_treatment, reporting_currency_conversion,
                       date_field, applicable_filters, data_quality_requirements,
                       classification, example_business_questions, known_limitations
                FROM metadata.metric_catalog
                WHERE metric_id = %s
                LIMIT 1;
                """,
                (metric_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            row["relevant_columns"] = (
                row["relevant_columns"]
                if isinstance(row["relevant_columns"], list)
                else json.loads(row["relevant_columns"])
            )
            row["example_business_questions"] = (
                row["example_business_questions"]
                if isinstance(row["example_business_questions"], list)
                else json.loads(row["example_business_questions"])
            )
            row["classification"] = DataClassification(row["classification"])
            return FinancialMetric(**row)
