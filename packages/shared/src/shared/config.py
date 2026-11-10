"""Centralized configuration management using Pydantic Settings.

Reads configuration from environment variables or .env file with explicit
type validation and strict defaults for development safety.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # PostgreSQL Database Settings
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="analytics_platform", alias="POSTGRES_DB")
    postgres_user: str = Field(default="analytics_user", alias="POSTGRES_USER")
    postgres_password: str = Field(
        default="analytics_dev_password_change_me",
        alias="POSTGRES_PASSWORD",
    )
    postgres_schema: str = Field(default="public", alias="POSTGRES_SCHEMA")

    # DuckDB In-Memory / Embedded Settings
    duckdb_database: str = Field(default=":memory:", alias="DUCKDB_DATABASE")

    # Database Pool & Limits
    db_pool_min_size: int = Field(default=2, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=5, alias="DB_POOL_MAX_SIZE")
    db_timeout_seconds: int = Field(default=30, alias="DB_TIMEOUT_SECONDS")

    @property
    def postgres_connection_string(self) -> str:
        """Construct PostgreSQL connection URI for psycopg3."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton application settings instance."""
    return Settings()
