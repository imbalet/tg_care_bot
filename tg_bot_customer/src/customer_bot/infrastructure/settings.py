from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from customer_bot.infrastructure.logger import LogLevel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: LogLevel = Field(default=LogLevel.INFO, validation_alias="LOG_LEVEL")

    bot_token: str = Field(validation_alias="BOT_TOKEN")

    backend_scheme: str = Field(default="http", validation_alias="BACKEND_SCHEME")
    backend_host: str = Field(default="localhost", validation_alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, validation_alias="BACKEND_PORT")
    service_key: str = Field(
        default="dev-service-key",
        validation_alias="SERVICE_KEY",
    )
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=1, validation_alias="REDIS_DB")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")

    request_timeout_seconds: float = Field(
        default=5.0,
        validation_alias="REQUEST_TIMEOUT_SECONDS",
    )

    @property
    def backend_url(self) -> str:
        return f"{self.backend_scheme}://{self.backend_host}:{self.backend_port}"

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            password = quote_plus(self.redis_password)
            return f"redis://:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore
