-- Provision least-privilege analytics_reader role for read-only analytical queries.
-- Variables :reader_user and :reader_password should be provided via psql -v,
-- or provisioned securely using data_platform.security.provision_reader.

\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'analytics_reader') THEN
        CREATE ROLE analytics_reader WITH LOGIN;
    END IF;
END $$;

ALTER ROLE analytics_reader SET statement_timeout = '5000ms';

-- Revoke all schema and table access from public and internal schemas
REVOKE ALL ON SCHEMA public FROM analytics_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM analytics_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics REVOKE ALL ON TABLES FROM analytics_reader;

DO $$
DECLARE
    s text;
BEGIN
    FOR s IN SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('raw', 'staging', 'intermediate', 'metadata')
    LOOP
        EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM analytics_reader', s);
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM analytics_reader', s);
    END LOOP;
END $$;

-- Revoke all tables in analytics schema
REVOKE ALL ON ALL TABLES IN SCHEMA analytics FROM analytics_reader;

-- Grant USAGE on analytics schema
GRANT USAGE ON SCHEMA analytics TO analytics_reader;

-- Grant SELECT ONLY on the 6 certified queryable analytical marts
GRANT SELECT ON analytics.dim_accounts TO analytics_reader;
GRANT SELECT ON analytics.dim_customers TO analytics_reader;
GRANT SELECT ON analytics.fct_customer_revenue TO analytics_reader;
GRANT SELECT ON analytics.fct_fee_assessments TO analytics_reader;
GRANT SELECT ON analytics.fct_fee_collections TO analytics_reader;
GRANT SELECT ON analytics.fct_transactions TO analytics_reader;
