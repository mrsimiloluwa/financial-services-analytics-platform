"""Provisioning least-privilege analytics_reader PostgreSQL role using environment credentials."""

from __future__ import annotations

import logging
from typing import Any

from psycopg import sql
from shared.config import Settings, get_settings
from shared.db import (
    ensure_test_database_exists,
    get_postgres_connection,
    get_test_postgres_connection,
)

logger = logging.getLogger(__name__)

APPROVED_QUERYABLE_MARTS = [
    "dim_accounts",
    "dim_customers",
    "fct_customer_revenue",
    "fct_fee_assessments",
    "fct_fee_collections",
    "fct_transactions",
]


def provision_analytics_reader_role(
    conn: Any,
    settings: Settings | None = None,
    approved_marts: list[str] | None = None,
) -> None:
    """Configure least-privilege analytics_reader role on the active PostgreSQL database connection."""
    cfg = settings or get_settings()
    if cfg.is_duckdb:
        logger.info("Running in DuckDB mode; skipping PostgreSQL role provisioning.")
        return

    reader_user = cfg.postgres_reader_user
    reader_password = cfg.postgres_reader_password
    marts = approved_marts or APPROVED_QUERYABLE_MARTS

    with conn.cursor() as cur:
        # 1. Create or update role with configured password from environment
        cur.execute(
            """
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = %s;
            """,
            (reader_user,),
        )
        role_exists = cur.fetchone() is not None

        if not role_exists:
            cur.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {};").format(
                    sql.Identifier(reader_user),
                    sql.Literal(reader_password),
                )
            )
            logger.info("Created PostgreSQL role '%s'", reader_user)
        else:
            cur.execute(
                sql.SQL("ALTER ROLE {} WITH PASSWORD {};").format(
                    sql.Identifier(reader_user),
                    sql.Literal(reader_password),
                )
            )
            logger.info("Updated password for existing PostgreSQL role '%s'", reader_user)

        # 2. Hard statement timeout constraint at role level
        cur.execute(
            sql.SQL("ALTER ROLE {} SET statement_timeout = '5000ms';").format(
                sql.Identifier(reader_user)
            )
        )

        # 3. Strip all default and schema-level privileges across database
        cur.execute(
            sql.SQL("REVOKE ALL ON SCHEMA public FROM {};").format(sql.Identifier(reader_user))
        )
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {};"
            ).format(sql.Identifier(reader_user))
        )
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics REVOKE ALL ON TABLES FROM {};"
            ).format(sql.Identifier(reader_user))
        )

        # Revoke access to all non-mart schemas if they exist
        for disallowed_schema in ["raw", "staging", "intermediate", "metadata", "public"]:
            cur.execute(
                """
                SELECT 1 FROM information_schema.schemata WHERE schema_name = %s;
                """,
                (disallowed_schema,),
            )
            if cur.fetchone():
                cur.execute(
                    sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {};").format(
                        sql.Identifier(disallowed_schema),
                        sql.Identifier(reader_user),
                    )
                )
                cur.execute(
                    sql.SQL("REVOKE ALL ON SCHEMA {} FROM {};").format(
                        sql.Identifier(disallowed_schema),
                        sql.Identifier(reader_user),
                    )
                )

        # 4. In analytics schema: revoke everything first
        cur.execute(
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA analytics FROM {};").format(
                sql.Identifier(reader_user)
            )
        )

        # 5. Grant USAGE on analytics schema
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA analytics TO {};").format(sql.Identifier(reader_user))
        )

        # 6. Explicitly grant SELECT strictly on approved queryable marts only
        for table_name in marts:
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'analytics' AND table_name = %s;
                """,
                (table_name,),
            )
            if cur.fetchone():
                cur.execute(
                    sql.SQL("GRANT SELECT ON analytics.{} TO {};").format(
                        sql.Identifier(table_name),
                        sql.Identifier(reader_user),
                    )
                )
                logger.info("Granted SELECT on analytics.%s to %s", table_name, reader_user)
            else:
                logger.warning("Table analytics.%s does not exist; skipped grant", table_name)

        conn.commit()
        logger.info("Successfully provisioned %s with least-privilege mart access.", reader_user)


def provision_both_environments(settings: Settings | None = None) -> None:
    """Provision least-privilege analytics_reader across both dev and test databases."""
    cfg = settings or get_settings()
    if cfg.is_duckdb:
        logger.info("Running in DuckDB mode; skipping PostgreSQL role provisioning.")
        return

    # DEV database
    logger.info("Provisioning analytics_reader on DEV database '%s'...", cfg.postgres_db)
    with get_postgres_connection(cfg) as dev_conn:
        provision_analytics_reader_role(dev_conn, cfg)

    # TEST database (if distinct from DEV)
    if cfg.postgres_db != cfg.postgres_test_db:
        ensure_test_database_exists(cfg)
        logger.info("Provisioning analytics_reader on TEST database '%s'...", cfg.postgres_test_db)
        with get_test_postgres_connection(cfg) as test_conn:
            provision_analytics_reader_role(test_conn, cfg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    provision_both_environments()
