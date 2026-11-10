"""Unit tests for configuration loading and validation."""

from shared.config import Settings


def test_default_settings() -> None:
    """Verify default development configuration settings."""
    settings = Settings()
    assert settings.app_env in {"development", "testing"}
    assert settings.postgres_port == 5432
    assert settings.postgres_db == "analytics_platform"
    assert settings.duckdb_database == ":memory:"


def test_postgres_connection_string() -> None:
    """Verify proper formatting of PostgreSQL connection URI."""
    settings = Settings(
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_HOST="db.internal",
        POSTGRES_PORT=5433,
        POSTGRES_DB="test_db",
    )
    expected = "postgresql://test_user:test_password@db.internal:5433/test_db"
    assert settings.postgres_connection_string == expected
