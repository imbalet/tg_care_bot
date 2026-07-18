from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = Field(validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_name: str = Field(validation_alias="DB_NAME")
    db_user: str = Field(validation_alias="DB_USER")
    db_pass: str = Field(validation_alias="DB_PASS")
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    service_key: str = Field(validation_alias="SERVICE_KEY")
    app_name: str = Field(default="we-are-close-api", validation_alias="APP_NAME")
    environment: Literal["local", "test", "production"] = Field(
        default="local",
        validation_alias="APP_ENV",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    readiness_timeout_seconds: float = Field(
        default=1.0,
        validation_alias="READINESS_TIMEOUT_SECONDS",
    )
    worker_poll_interval_seconds: float = Field(
        default=1.0,
        validation_alias="WORKER_POLL_INTERVAL_SECONDS",
    )
    worker_batch_limit: int = Field(default=50, validation_alias="WORKER_BATCH_LIMIT")
    admin_session_ttl_seconds: int = Field(
        default=86_400,
        validation_alias="ADMIN_SESSION_TTL_SECONDS",
    )
    dadata_api_key: str = Field(default="", validation_alias="DADATA_API_KEY")
    dadata_secret_key: str = Field(default="", validation_alias="DADATA_SECRET_KEY")
    dadata_base_url: str = Field(
        default="https://suggestions.dadata.ru",
        validation_alias="DADATA_BASE_URL",
    )
    dadata_timeout_seconds: float = Field(
        default=2.0,
        validation_alias="DADATA_TIMEOUT_SECONDS",
    )
    dadata_retry_count: int = Field(default=1, validation_alias="DADATA_RETRY_COUNT")
    s3_endpoint_url: str = Field(validation_alias="S3_ENDPOINT_URL")
    s3_access_key_id: str = Field(validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(validation_alias="S3_SECRET_ACCESS_KEY")
    s3_bucket: str = Field(validation_alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", validation_alias="S3_REGION")
    s3_signed_url_ttl_seconds: int = Field(
        default=900,
        validation_alias="S3_SIGNED_URL_TTL_SECONDS",
    )
    payment_provider: Literal["tbank_test"] = Field(
        default="tbank_test",
        validation_alias="PAYMENT_PROVIDER",
    )
    tbank_base_url: str = Field(
        default="https://rest-api-test.tinkoff.ru/v2",
        validation_alias="TBANK_BASE_URL",
    )
    tbank_terminal_key: str = Field(default="", validation_alias="TBANK_TERMINAL_KEY")
    tbank_password: str = Field(default="", validation_alias="TBANK_PASSWORD")
    tbank_timeout_seconds: float = Field(
        default=5.0,
        validation_alias="TBANK_TIMEOUT_SECONDS",
    )
    payment_receipt_taxation: str = Field(
        default="osn",
        validation_alias="PAYMENT_RECEIPT_TAXATION",
    )
    payment_receipt_tax: str = Field(
        default="vat20",
        validation_alias="PAYMENT_RECEIPT_TAX",
    )
    payment_receipt_method: str = Field(
        default="full_prepayment",
        validation_alias="PAYMENT_RECEIPT_METHOD",
    )
    payment_receipt_object: str = Field(
        default="service",
        validation_alias="PAYMENT_RECEIPT_OBJECT",
    )
    payment_receipt_defaults_allowed: bool = Field(
        default=True,
        validation_alias="PAYMENT_RECEIPT_DEFAULTS_ALLOWED",
    )

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_pass)
        return (
            "postgresql+asyncpg://"
            f"{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            password = quote_plus(self.redis_password)
            return f"redis://:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
