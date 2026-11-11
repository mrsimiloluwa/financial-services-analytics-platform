"""Pydantic schemas and typed definitions for the Governed Financial Metadata Catalog."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DataClassification(StrEnum):
    """Governed data classification sensitivity tiers."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class ColumnMetadata(BaseModel):
    """Catalog metadata for an individual model or source column."""

    name: str
    data_type: str
    ordinal_position: int | None = None
    description: str = "Undocumented column."
    classification: DataClassification = DataClassification.INTERNAL
    is_nullable: bool = True
    tests: list[str] = Field(default_factory=list)
    upstream_columns: list[str] = Field(default_factory=list)


class ModelMetadata(BaseModel):
    """Catalog metadata for a dbt dimensional or transformation model."""

    model_config = {"protected_namespaces": ()}

    model_id: str
    name: str
    layer: str
    database: str
    schema_name: str
    relation_name: str
    materialization: str
    description: str = "Undocumented model."
    tags: list[str] = Field(default_factory=list)
    file_path: str | None = None
    grain: str | None = None
    classification: DataClassification = DataClassification.INTERNAL
    is_queryable: bool = False
    upstream_models: list[str] = Field(default_factory=list)
    upstream_sources: list[str] = Field(default_factory=list)
    model_tests: list[str] = Field(default_factory=list)
    columns: dict[str, ColumnMetadata] = Field(default_factory=dict)


class SourceMetadata(BaseModel):
    """Catalog metadata for a raw ingested database source."""

    source_id: str
    source_name: str
    table_name: str
    database: str
    schema_name: str
    description: str = "Undocumented raw source table."
    columns: dict[str, ColumnMetadata] = Field(default_factory=dict)
    classification: DataClassification = DataClassification.CONFIDENTIAL
    downstream_models: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)


class LineageEdge(BaseModel):
    """Directed dependency edge between data nodes (source, model, or column)."""

    source_id: str
    target_id: str
    edge_type: str  # MODEL_TO_MODEL, SOURCE_TO_MODEL, COLUMN_TO_COLUMN
    details: dict[str, Any] = Field(default_factory=dict)


class FinancialMetric(BaseModel):
    """Governed definition of an enterprise financial performance metric."""

    metric_id: str
    metric_name: str
    business_definition: str
    formula: str
    source_model: str
    relevant_columns: list[str]
    grain: str
    aggregation_behavior: str
    native_currency_treatment: str
    reporting_currency_conversion: str
    date_field: str
    applicable_filters: str | None = None
    data_quality_requirements: str | None = None
    classification: DataClassification = DataClassification.INTERNAL
    example_business_questions: list[str] = Field(default_factory=list)
    known_limitations: str | None = None


class ArtifactRun(BaseModel):
    """Execution telemetry record for published dbt compilation artifacts."""

    run_id: str
    environment: str
    created_at: datetime
    dbt_version: str
    adapter_type: str
    target_name: str
    database_name: str
    schema_name: str
    total_models: int
    total_sources: int
    total_tests: int
    build_status: str
    artifact_path: str
    is_latest: bool = False


class QueryContext(BaseModel):
    """Contextual metadata package supplied to AI reasoning and text-to-SQL layers."""

    model_config = {"protected_namespaces": ()}

    model_name: str
    description: str
    business_purpose: str
    grain: str
    classification: DataClassification
    columns: dict[str, str]  # col_name -> "type: description"
    available_metrics: list[str]
    date_fields: list[str]
    currency_fields: list[str]
    safe_joins: list[dict[str, str]]
    example_questions: list[str]
    restrictions: list[str]
