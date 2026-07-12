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

    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_name: str = Field(default="we_are_close", validation_alias="DB_NAME")
    db_user: str = Field(default="postgres", validation_alias="DB_USER")
    db_pass: str = Field(default="postgres", validation_alias="DB_PASS")
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    service_key: str = Field(
        default="dev-service-key",
        validation_alias="SERVICE_KEY",
    )
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


__all__ = ["Settings", "get_settings"]
