"""Configuration settings for the API service."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Jaeger configuration
    jaeger_query_url: str = "http://jaeger:16686"

    # OpenTelemetry configuration
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"
    otel_service_name: str = "opentrace-api"

    # Security
    approval_required: bool = True

    # Allowlisted paths for recording (regex patterns)
    record_allowlist: list[str] = [
        r"^/health$",
        r"^/demo/.*",
        r"^/api/.*",
    ]

    # Repo analysis
    repos_base_path: str = "/tmp/repos"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
