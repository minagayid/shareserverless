from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ShareServerless Scheduler"
    app_env: str = "development"
    debug: bool = True

    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]

    # Database
    database_url: str = "postgresql+asyncpg://ss:ss@localhost:5432/shareserverless"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT / Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "ES256"
    jwt_access_token_expire_minutes: int = 30

    # gRPC
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051

    # Node registration
    min_reputation_to_accept_tasks: float = 0.0
    heartbeat_interval_seconds: int = 30
    heartbeat_timeout_seconds: int = 90

    # Task defaults
    default_task_timeout_seconds: int = 300
    max_retries: int = 3
    verification_nodes_required: int = 2

    # Consensus
    consensus_accuracy_threshold: float = 0.8

    # Monitoring
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # Logging
    log_level: str = "INFO"


settings = Settings()
