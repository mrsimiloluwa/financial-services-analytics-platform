-- =============================================================================
-- GOVERNED FINANCIAL METADATA CATALOG SCHEMA DEFINITIONS
-- Enterprise AI Analytics Platform for Financial Services
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS metadata;

-- 1. Artifact Execution Runs & Snapshot Manifests
CREATE TABLE IF NOT EXISTS metadata.artifact_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    environment VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    dbt_version VARCHAR(32) NOT NULL,
    adapter_type VARCHAR(32) NOT NULL,
    target_name VARCHAR(32) NOT NULL,
    database_name VARCHAR(64) NOT NULL,
    schema_name VARCHAR(64) NOT NULL,
    total_models INT NOT NULL,
    total_sources INT NOT NULL,
    total_tests INT NOT NULL,
    build_status VARCHAR(32) NOT NULL,
    artifact_path VARCHAR(255) NOT NULL,
    is_latest BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_artifact_runs_env_latest ON metadata.artifact_runs(environment, is_latest);

-- 2. Data Classifications Catalog
CREATE TABLE IF NOT EXISTS metadata.classification_catalog (
    classification_id VARCHAR(32) PRIMARY KEY,
    display_name VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    sensitivity_level INT NOT NULL,
    handling_rules TEXT NOT NULL
);

-- Seed standard governance classifications
INSERT INTO metadata.classification_catalog (classification_id, display_name, description, sensitivity_level, handling_rules)
VALUES
    ('PUBLIC', 'Public Information', 'Freely sharable information with no regulatory or competitive sensitivity.', 1, 'No restriction on display, export, or usage.'),
    ('INTERNAL', 'Internal Governance', 'Platform definitions, model descriptions, and aggregated metrics intended for enterprise staff.', 2, 'Available across internal platform services. Do not expose externally.'),
    ('CONFIDENTIAL', 'Confidential Banking Data', 'Synthetic customer, account, and financial transaction identifiers and amounts.', 3, 'Mask or redact raw identifier values in metadata and model contexts.'),
    ('RESTRICTED', 'Restricted Security Secrets', 'Credentials, authentication keys, passwords, and private signing keys.', 4, 'Strictly forbidden in analytical models, metadata catalogs, and logs.')
ON CONFLICT (classification_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sensitivity_level = EXCLUDED.sensitivity_level,
    handling_rules = EXCLUDED.handling_rules;

-- 3. Models Catalog
CREATE TABLE IF NOT EXISTS metadata.model_catalog (
    model_id VARCHAR(255) PRIMARY KEY,
    model_name VARCHAR(128) NOT NULL,
    layer VARCHAR(32) NOT NULL,
    database_name VARCHAR(64) NOT NULL,
    schema_name VARCHAR(64) NOT NULL,
    relation_name VARCHAR(128) NOT NULL,
    materialization VARCHAR(32) NOT NULL,
    description TEXT,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    file_path VARCHAR(255),
    grain VARCHAR(255),
    classification VARCHAR(32) NOT NULL DEFAULT 'INTERNAL' REFERENCES metadata.classification_catalog(classification_id),
    is_queryable BOOLEAN NOT NULL DEFAULT FALSE,
    upstream_models JSONB NOT NULL DEFAULT '[]'::jsonb,
    upstream_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_tests JSONB NOT NULL DEFAULT '[]'::jsonb,
    snapshot_id VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_catalog_name ON metadata.model_catalog(model_name);
CREATE INDEX IF NOT EXISTS idx_model_catalog_queryable ON metadata.model_catalog(is_queryable);
CREATE INDEX IF NOT EXISTS idx_model_catalog_layer ON metadata.model_catalog(layer);

-- 4. Columns Catalog
CREATE TABLE IF NOT EXISTS metadata.column_catalog (
    column_id VARCHAR(512) PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL REFERENCES metadata.model_catalog(model_id) ON DELETE CASCADE,
    column_name VARCHAR(128) NOT NULL,
    ordinal_position INT,
    data_type VARCHAR(64) NOT NULL,
    description TEXT,
    classification VARCHAR(32) NOT NULL DEFAULT 'INTERNAL' REFERENCES metadata.classification_catalog(classification_id),
    is_nullable BOOLEAN NOT NULL DEFAULT TRUE,
    tests JSONB NOT NULL DEFAULT '[]'::jsonb,
    upstream_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
    snapshot_id VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_column_catalog_model ON metadata.column_catalog(model_id);
CREATE INDEX IF NOT EXISTS idx_column_catalog_name ON metadata.column_catalog(column_name);

-- 5. Raw Sources Catalog
CREATE TABLE IF NOT EXISTS metadata.source_catalog (
    source_id VARCHAR(255) PRIMARY KEY,
    source_name VARCHAR(64) NOT NULL,
    table_name VARCHAR(64) NOT NULL,
    database_name VARCHAR(64) NOT NULL,
    schema_name VARCHAR(64) NOT NULL,
    description TEXT,
    column_count INT NOT NULL DEFAULT 0,
    classification VARCHAR(32) NOT NULL DEFAULT 'CONFIDENTIAL' REFERENCES metadata.classification_catalog(classification_id),
    downstream_models JSONB NOT NULL DEFAULT '[]'::jsonb,
    tests JSONB NOT NULL DEFAULT '[]'::jsonb,
    snapshot_id VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_catalog_table ON metadata.source_catalog(source_name, table_name);

-- 6. Governed Financial Metric Catalog
CREATE TABLE IF NOT EXISTS metadata.metric_catalog (
    metric_id VARCHAR(64) PRIMARY KEY,
    metric_name VARCHAR(128) NOT NULL,
    business_definition TEXT NOT NULL,
    formula TEXT NOT NULL,
    source_model VARCHAR(128) NOT NULL,
    relevant_columns JSONB NOT NULL,
    grain VARCHAR(255) NOT NULL,
    aggregation_behavior VARCHAR(64) NOT NULL,
    native_currency_treatment TEXT NOT NULL,
    reporting_currency_conversion TEXT NOT NULL,
    date_field VARCHAR(64) NOT NULL,
    applicable_filters TEXT,
    data_quality_requirements TEXT,
    classification VARCHAR(32) NOT NULL DEFAULT 'INTERNAL' REFERENCES metadata.classification_catalog(classification_id),
    example_business_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    known_limitations TEXT,
    snapshot_id VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metric_catalog_model ON metadata.metric_catalog(source_model);

-- 7. Lineage Graph Edges
CREATE TABLE IF NOT EXISTS metadata.lineage_edges (
    edge_id VARCHAR(512) PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL,
    target_id VARCHAR(255) NOT NULL,
    edge_type VARCHAR(32) NOT NULL,
    details JSONB,
    snapshot_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_edges_source ON metadata.lineage_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_target ON metadata.lineage_edges(target_id);
