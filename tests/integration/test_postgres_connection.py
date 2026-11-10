"""Integration test for PostgreSQL connectivity."""

import os

import psycopg
import pytest
from shared.config import Settings
from shared.db import get_postgres_connection


def test_postgres_live_connection() -> None:
    """Attempt live connection to PostgreSQL container if reachable."""
    settings = Settings()
    try:
        with get_postgres_connection(settings) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 AS alive, current_database();")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 1
            assert row[1] == settings.postgres_db
    except psycopg.OperationalError as exc:
        if os.getenv("CI") == "true" or settings.app_env == "testing":
            pytest.fail(f"PostgreSQL connection failed in CI/testing environment: {exc}")
        pytest.skip(
            f"PostgreSQL container not accessible locally (start with 'docker compose up -d'): {exc}"
        )
