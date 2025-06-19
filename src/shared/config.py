"""
Tel-Insights Configuration Module

Centralized configuration management using Pydantic Settings.
This module handles all environment variables and application settings.
"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field(
        default="postgresql://username:password@localhost:5432/tel_insights",
        env="DATABASE_URL",
        description="PostgreSQL database connection URL"
    )
    pool_size: int = Field(
        default=10,
        env="DATABASE_POOL_SIZE",
        description="Database connection pool size"
    )
    max_overflow: int = Field(
        default=20,
        env="DATABASE_MAX_OVERFLOW",
        description="Maximum database connection overflow"
    )

    class Config:
        env_prefix = "DATABASE_"


class RabbitMQSettings(BaseSettings):
    """RabbitMQ message queue configuration settings."""
    
    url: str = Field(
        default="amqp://guest:guest@localhost:5672/",
        env="RABBITMQ_URL",
        description="RabbitMQ connection URL"
    )
    exchange: str = Field(
        default="tel_insights",
        env="RABBITMQ_EXCHANGE",
        description="RabbitMQ exchange name"
    )
    queue_new_message: str = Field(
        default="new_message_received",
        env="RABBITMQ_QUEUE_NEW_MESSAGE",
        description="Queue for new message events"
    )
    queue_dead_letter: str = Field(
        default="dead_letter",
        env="RABBITMQ_QUEUE_DEAD_LETTER",
        description="Dead letter queue for failed messages"
    )

    class Config:
        env_prefix = "RABBITMQ_"


class TelegramSettings(BaseSettings):
    """Telegram API configuration settings."""
    
    api_id: str = Field(
        env="TELEGRAM_API_ID",
        description="Telegram API ID for user client"
    )
    api_hash: str = Field(
        env="TELEGRAM_API_HASH",
        description="Telegram API hash for user client"
    )
    session_file: str = Field(
        default="telegram_aggregator.session",
        env="TELEGRAM_SESSION_FILE",
        description="Telegram session file path"
    )
    bot_token: str = Field(
        env="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token for bot client"
    )
    bot_username: str = Field(
        env="TELEGRAM_BOT_USERNAME",
        description="Telegram bot username"
    )

    class Config:
        env_prefix = "TELEGRAM_"


class LLMSettings(BaseSettings):
    """Large Language Model API configuration settings."""
    
    google_api_key: Optional[str] = Field(
        default=None,
        env="GOOGLE_API_KEY",
        description="Google Gemini API key"
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        env="OPENAI_API_KEY",
        description="OpenAI API key"
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        env="ANTHROPIC_API_KEY",
        description="Anthropic Claude API key"
    )
    default_model: str = Field(
        default="gemini-2.5-pro",
        env="DEFAULT_LLM_MODEL",
        description="Default LLM model to use"
    )
    max_retries: int = Field(
        default=3,
        env="LLM_MAX_RETRIES",
        description="Maximum retries for LLM API calls"
    )
    timeout_seconds: int = Field(
        default=60,
        env="LLM_TIMEOUT_SECONDS",
        description="LLM API timeout in seconds"
    )


class GCSSettings(BaseSettings):
    """Google Cloud Storage configuration settings."""
    
    bucket_name: str = Field(
        default="tel-insights-media",
        env="GCS_BUCKET_NAME",
        description="Google Cloud Storage bucket name"
    )
    credentials_path: Optional[str] = Field(
        default=None,
        env="GCS_CREDENTIALS_PATH",
        description="Path to GCS service account credentials JSON file"
    )

    class Config:
        env_prefix = "GCS_"


class ServiceURLs(BaseSettings):
    """Microservice URL configuration."""
    
    aggregator_url: str = Field(
        default="http://localhost:8001",
        env="AGGREGATOR_SERVICE_URL",
        description="Aggregator service URL"
    )
    ai_analysis_url: str = Field(
        default="http://localhost:8002",
        env="AI_ANALYSIS_SERVICE_URL",
        description="AI Analysis service URL"
    )
    smart_analysis_url: str = Field(
        default="http://localhost:8003",
        env="SMART_ANALYSIS_SERVICE_URL",
        description="Smart Analysis service URL"
    )
    alerting_url: str = Field(
        default="http://localhost:8004",
        env="ALERTING_SERVICE_URL",
        description="Alerting service URL"
    )


class SecuritySettings(BaseSettings):
    """Security and encryption configuration settings."""
    
    secret_key: str = Field(
        env="SECRET_KEY",
        description="Application secret key"
    )
    jwt_secret_key: str = Field(
        env="JWT_SECRET_KEY",
        description="JWT token secret key"
    )
    encryption_key: str = Field(
        env="ENCRYPTION_KEY",
        description="Data encryption key"
    )


class AlertSettings(BaseSettings):
    """Alert configuration settings."""
    
    default_threshold: int = Field(
        default=20,
        env="DEFAULT_ALERT_THRESHOLD",
        description="Default alert threshold for frequency-based alerts"
    )
    default_window_minutes: int = Field(
        default=60,
        env="DEFAULT_ALERT_WINDOW_MINUTES",
        description="Default time window for alerts in minutes"
    )
    cooldown_minutes: int = Field(
        default=30,
        env="ALERT_COOLDOWN_MINUTES",
        description="Alert cooldown period in minutes"
    )


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration settings."""
    
    prometheus_port: int = Field(
        default=9090,
        env="PROMETHEUS_PORT",
        description="Prometheus metrics server port"
    )
    metrics_enabled: bool = Field(
        default=True,
        env="METRICS_ENABLED",
        description="Enable metrics collection"
    )
    log_level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="Application log level"
    )


class ApplicationSettings(BaseSettings):
    """Main application configuration settings."""
    
    debug: bool = Field(
        default=False,
        env="DEBUG",
        description="Enable debug mode"
    )
    environment: str = Field(
        default="development",
        env="ENVIRONMENT",
        description="Application environment (development, staging, production)"
    )
    monitored_channels: List[str] = Field(
        default_factory=list,
        env="MONITORED_CHANNELS",
        description="List of Telegram channels to monitor"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class Settings(BaseSettings):
    """Main settings class that aggregates all configuration sections."""
    
    database: DatabaseSettings = DatabaseSettings()
    rabbitmq: RabbitMQSettings = RabbitMQSettings()
    telegram: TelegramSettings = TelegramSettings()
    llm: LLMSettings = LLMSettings()
    gcs: GCSSettings = GCSSettings()
    service_urls: ServiceURLs = ServiceURLs()
    security: SecuritySettings = SecuritySettings()
    alerts: AlertSettings = AlertSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    app: ApplicationSettings = ApplicationSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings 