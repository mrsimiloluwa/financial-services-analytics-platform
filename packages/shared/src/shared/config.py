"""Centralized configuration management using Pydantic Settings.

Reads configuration from environment variables or .env file with explicit
type validation and strict defaults for development safety.
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_streamlit_secrets() -> None:
    """Inject Streamlit secrets into environment variables if running in Streamlit Cloud."""
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            for key, val in st.secrets.items():
                if isinstance(val, dict):
                    for sub_k, sub_v in val.items():
                        os.environ.setdefault(sub_k.upper(), str(sub_v))
                elif isinstance(val, (str, int, float, bool)):
                    os.environ.setdefault(key.upper(), str(val))
    except Exception:
        # Streamlit not running or secrets not configured
        pass


def _detect_default_database_backend() -> str:
    """Detect default database backend based on environment and connectivity."""
    # 1. Respect explicit environment variable if set
    backend = os.environ.get("DATABASE_BACKEND")
    if backend:
        return backend.lower()

    # 2. Check Streamlit secrets if running inside Streamlit
    try:
        import streamlit as st

        if hasattr(st, "secrets") and "DATABASE_BACKEND" in st.secrets:
            return str(st.secrets["DATABASE_BACKEND"]).lower()
    except Exception:
        pass

    # 3. If POSTGRES_HOST is set to a remote host (e.g. Docker container 'postgres' or Neon), use postgres
    host = os.environ.get("POSTGRES_HOST")
    if host and host not in ("localhost", "127.0.0.1", ""):
        return "postgres"

    # 4. Probe localhost:5432 with a fast non-blocking timeout
    # If not listening (e.g. Streamlit Community Cloud serverless container), default to duckdb
    import socket

    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    try:
        with socket.create_connection((host or "127.0.0.1", port), timeout=0.15):
            return "postgres"
    except OSError:
        return "duckdb"


_load_streamlit_secrets()


class Settings(BaseSettings):
    """Application-wide settings validated at runtime."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    app_env: Literal["development", "testing", "staging", "production"] = Field(
        default="development",
        alias="APP_ENV",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG")
    reporting_base_currency: Literal["EUR", "USD", "GBP"] = Field(
        default="EUR",
        alias="REPORTING_BASE_CURRENCY",
    )

    # Database Backend Selection (postgres vs duckdb with auto-detection)
    database_backend: str = Field(
        default_factory=_detect_default_database_backend,
        alias="DATABASE_BACKEND",
    )

    # PostgreSQL Database Settings
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="analytics_platform", alias="POSTGRES_DB")
    postgres_test_db: str = Field(
        default="analytics_platform_test",
        alias="POSTGRES_TEST_DB",
    )
    postgres_user: str = Field(default="analytics_user", alias="POSTGRES_USER")
    postgres_password: str = Field(
        default="analytics_dev_password_change_me",
        alias="POSTGRES_PASSWORD",
    )
    postgres_schema: str = Field(default="public", alias="POSTGRES_SCHEMA")

    # PostgreSQL Read-Only Analytics Reader (Least Privilege Role)
    postgres_reader_user: str = Field(default="analytics_reader", alias="POSTGRES_READER_USER")
    postgres_reader_password: str = Field(
        default="analytics_reader_secret",
        alias="POSTGRES_READER_PASSWORD",
    )
    postgres_sslmode: str | None = Field(default=None, alias="POSTGRES_SSLMODE")

    # LLM & AI Services Configuration
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    llm_model: str = Field(default="mock-model", alias="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    llm_timeout_seconds: int = Field(default=30, alias="LLM_TIMEOUT_SECONDS")

    # API Security & Rate Limiting (Phase 7)
    api_auth_enabled: bool = Field(default=False, alias="API_AUTH_ENABLED")
    api_key: str | None = Field(default=None, alias="API_KEY")
    api_base_url: str | None = Field(default=None, alias="API_BASE_URL")
    rate_limit_per_minute: int = Field(default=120, alias="RATE_LIMIT_PER_MINUTE")

    # DuckDB In-Memory / Embedded Settings
    duckdb_database: str = Field(default=":memory:", alias="DUCKDB_DATABASE")

    # Database Pool & Limits
    db_pool_min_size: int = Field(default=2, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=5, alias="DB_POOL_MAX_SIZE")
    db_timeout_seconds: int = Field(default=30, alias="DB_TIMEOUT_SECONDS")

    @property
    def is_duckdb(self) -> bool:
        """Check whether execution should use embedded DuckDB over packaged sample marts."""
        return self.database_backend.lower() == "duckdb" or not bool(self.postgres_host)

    @property
    def postgres_connection_string(self) -> str:
        """Construct PostgreSQL connection URI for psycopg3."""
        ssl_suffix = f"?sslmode={self.postgres_sslmode}" if self.postgres_sslmode else ""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}{ssl_suffix}"
        )

    @property
    def postgres_test_connection_string(self) -> str:
        """Construct PostgreSQL connection URI for isolated integration testing."""
        ssl_suffix = f"?sslmode={self.postgres_sslmode}" if self.postgres_sslmode else ""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_test_db}{ssl_suffix}"
        )

    @property
    def postgres_reader_connection_string(self) -> str:
        """Construct PostgreSQL connection URI for read-only analytics execution."""
        ssl_suffix = f"?sslmode={self.postgres_sslmode}" if self.postgres_sslmode else ""
        return (
            f"postgresql://{self.postgres_reader_user}:{self.postgres_reader_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}{ssl_suffix}"
        )

    @property
    def postgres_reader_test_connection_string(self) -> str:
        """Construct PostgreSQL connection URI for read-only test database execution."""
        ssl_suffix = f"?sslmode={self.postgres_sslmode}" if self.postgres_sslmode else ""
        return (
            f"postgresql://{self.postgres_reader_user}:{self.postgres_reader_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_test_db}{ssl_suffix}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton application settings instance."""
    return Settings()
