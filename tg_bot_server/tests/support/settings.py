from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache

import pytest
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TestSettings(BaseSettings):
    """Typed configuration shared by integration and Compose E2E tests."""

    __test__ = False

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = Field(default="test", validation_alias="APP_ENV")
    app_name: str = Field(
        default="we-are-close-test",
        validation_alias="APP_NAME",
    )
    log_level: str = Field(default="WARNING", validation_alias="LOG_LEVEL")
    db_host: str = Field(default="127.0.0.1", validation_alias="DB_HOST")
    db_port: int = Field(default=15432, validation_alias="DB_PORT")
    db_name: str = Field(default="we_are_close_test", validation_alias="DB_NAME")
    db_user: str = Field(default="postgres", validation_alias="DB_USER")
    db_pass: str = Field(default="postgres", validation_alias="DB_PASS")
    redis_host: str = Field(default="127.0.0.1", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=16379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    service_key: str = Field(
        default="test-service-key",
        validation_alias="SERVICE_KEY",
    )
    s3_endpoint_url: str = Field(
        default="http://127.0.0.1:19000",
        validation_alias="S3_ENDPOINT_URL",
    )
    s3_access_key_id: str = Field(
        default="minio",
        validation_alias="S3_ACCESS_KEY_ID",
    )
    s3_secret_access_key: str = Field(
        default="minio-password",
        validation_alias="S3_SECRET_ACCESS_KEY",
    )
    s3_bucket: str = Field(
        default="we-are-close-test-files",
        validation_alias="S3_BUCKET",
    )
    s3_region: str = Field(default="us-east-1", validation_alias="S3_REGION")
    s3_signed_url_ttl_seconds: int = Field(
        default=60,
        validation_alias="S3_SIGNED_URL_TTL_SECONDS",
    )
    customer_bot_token: str = Field(
        default="test-customer-token",
        validation_alias="CUSTOMER_BOT_TOKEN",
    )
    executor_bot_token: str = Field(
        default="test-executor-token",
        validation_alias="EXECUTOR_BOT_TOKEN",
    )
    telegram_api_base_url: str = Field(
        default="http://127.0.0.1:18081",
        validation_alias="TELEGRAM_API_BASE_URL",
    )
    dadata_api_key: str = Field(
        default="test-dadata-key",
        validation_alias="DADATA_API_KEY",
    )
    dadata_secret_key: str = Field(
        default="test-dadata-secret",
        validation_alias="DADATA_SECRET_KEY",
    )
    dadata_base_url: str = Field(
        default="http://127.0.0.1:18081",
        validation_alias="DADATA_BASE_URL",
    )
    payment_provider: str = Field(
        default="tbank_test",
        validation_alias="PAYMENT_PROVIDER",
    )
    tbank_base_url: str = Field(
        default="http://127.0.0.1:18081",
        validation_alias="TBANK_BASE_URL",
    )
    tbank_terminal_key: str = Field(
        default="test-terminal",
        validation_alias="TBANK_TERMINAL_KEY",
    )
    tbank_password: str = Field(
        default="test-password",
        validation_alias="TBANK_PASSWORD",
    )
    tbank_notification_url: str = Field(
        default="http://api:8000/api/payments/webhook",
        validation_alias="TBANK_NOTIFICATION_URL",
    )
    default_admin_email: str = Field(
        default="admin@test.local",
        validation_alias="DEFAULT_ADMIN_EMAIL",
    )
    default_admin_full_name: str = Field(
        default="Test Admin",
        validation_alias="DEFAULT_ADMIN_FULL_NAME",
    )
    default_admin_password: str = Field(
        default="test-password",
        validation_alias="DEFAULT_ADMIN_PASSWORD",
    )
    e2e_base_url: str = Field(
        default="http://api:8000",
        validation_alias="E2E_BASE_URL",
    )
    e2e_request_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="E2E_REQUEST_TIMEOUT_SECONDS",
    )
    test_admin_database: str = Field(
        default="postgres",
        validation_alias="TEST_ADMIN_DATABASE",
    )
    test_database_prefix: str = Field(
        default="we_are_close",
        validation_alias="TEST_DATABASE_PREFIX",
    )
    test_run_id: str = Field(default="local", validation_alias="TEST_RUN_ID")
    keep_test_databases: bool = Field(
        default=False,
        validation_alias="KEEP_TEST_DATABASES",
    )

    def as_environment(self, *, database_name: str | None = None) -> dict[str, str]:
        """Return the application environment required by test subprocesses."""

        values = {
            "APP_ENV": self.app_env,
            "APP_NAME": self.app_name,
            "LOG_LEVEL": self.log_level,
            "DB_HOST": self.db_host,
            "DB_PORT": str(self.db_port),
            "DB_NAME": database_name or self.db_name,
            "DB_USER": self.db_user,
            "DB_PASS": self.db_pass,
            "REDIS_HOST": self.redis_host,
            "REDIS_PORT": str(self.redis_port),
            "REDIS_DB": str(self.redis_db),
            "REDIS_PASSWORD": self.redis_password,
            "SERVICE_KEY": self.service_key,
            "S3_ENDPOINT_URL": self.s3_endpoint_url,
            "S3_ACCESS_KEY_ID": self.s3_access_key_id,
            "S3_SECRET_ACCESS_KEY": self.s3_secret_access_key,
            "S3_BUCKET": self.s3_bucket,
            "S3_REGION": self.s3_region,
            "S3_SIGNED_URL_TTL_SECONDS": str(self.s3_signed_url_ttl_seconds),
            "CUSTOMER_BOT_TOKEN": self.customer_bot_token,
            "EXECUTOR_BOT_TOKEN": self.executor_bot_token,
            "TELEGRAM_API_BASE_URL": self.telegram_api_base_url,
            "DADATA_API_KEY": self.dadata_api_key,
            "DADATA_SECRET_KEY": self.dadata_secret_key,
            "DADATA_BASE_URL": self.dadata_base_url,
            "PAYMENT_PROVIDER": self.payment_provider,
            "TBANK_BASE_URL": self.tbank_base_url,
            "TBANK_TERMINAL_KEY": self.tbank_terminal_key,
            "TBANK_PASSWORD": self.tbank_password,
            "TBANK_NOTIFICATION_URL": self.tbank_notification_url,
            "DEFAULT_ADMIN_EMAIL": self.default_admin_email,
            "DEFAULT_ADMIN_FULL_NAME": self.default_admin_full_name,
            "DEFAULT_ADMIN_PASSWORD": self.default_admin_password,
        }
        return values


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()


DEFAULT_TEST_ENVIRONMENT = get_test_settings().as_environment()


def apply_test_environment(
    monkeypatch: pytest.MonkeyPatch,
    overrides: Mapping[str, str] | None = None,
    *,
    preserve_existing: bool = False,
) -> None:
    settings = get_test_settings()
    values = {
        key: os.environ.get(key, value) if preserve_existing else value
        for key, value in settings.as_environment().items()
    }
    values.update(overrides or {})
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def environment_from_current_process() -> dict[str, str]:
    return {
        key: os.environ[key] for key in DEFAULT_TEST_ENVIRONMENT if key in os.environ
    }
