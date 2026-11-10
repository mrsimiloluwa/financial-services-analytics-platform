"""Unit tests for configuration loading and validation."""

from shared.config import Settings


def test_default_settings() -> None:
    """Verify default development configuration settings and schema field defaults."""
    # Verify underlying field defaults
    assert Settings.model_fields["postgres_db"].default == "analytics_platform"
    assert Settings.model_fields["postgres_port"].default == 5432
    assert Settings.model_fields["app_env"].default == "development"

    # Verify active runtime settings (permitting CI testing overrides)
    settings = Settings()
    assert settings.app_env in {"development", "testing"}
    assert settings.postgres_port == 5432
    assert settings.postgres_db in {"analytics_platform", "analytics_platform_test"}
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
