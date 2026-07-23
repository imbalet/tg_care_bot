from __future__ import annotations

import os
from collections.abc import Mapping

import pytest

DEFAULT_TEST_ENVIRONMENT: dict[str, str] = {
    "APP_ENV": "test",
    "APP_NAME": "we-are-close-test",
    "LOG_LEVEL": "WARNING",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "15432",
    "DB_NAME": "we_are_close_test",
    "DB_USER": "postgres",
    "DB_PASS": "postgres",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "16379",
    "REDIS_DB": "0",
    "REDIS_PASSWORD": "",
    "SERVICE_KEY": "test-service-key",
    "S3_ENDPOINT_URL": "http://127.0.0.1:19000",
    "S3_ACCESS_KEY_ID": "minio",
    "S3_SECRET_ACCESS_KEY": "minio-password",
    "S3_BUCKET": "we-are-close-test-files",
    "S3_REGION": "us-east-1",
    "S3_SIGNED_URL_TTL_SECONDS": "60",
    "CUSTOMER_BOT_TOKEN": "test-customer-token",
    "EXECUTOR_BOT_TOKEN": "test-executor-token",
    "TELEGRAM_API_BASE_URL": "http://127.0.0.1:18081",
    "DADATA_API_KEY": "test-dadata-key",
    "DADATA_SECRET_KEY": "test-dadata-secret",
    "DADATA_BASE_URL": "http://127.0.0.1:18081",
    "PAYMENT_PROVIDER": "tbank_test",
    "TBANK_BASE_URL": "http://127.0.0.1:18081",
    "TBANK_TERMINAL_KEY": "test-terminal",
    "TBANK_PASSWORD": "test-password",
    "TBANK_NOTIFICATION_URL": "http://api:8000/api/payments/webhook",
    "DEFAULT_ADMIN_EMAIL": "admin@test.local",
    "DEFAULT_ADMIN_FULL_NAME": "Test Admin",
    "DEFAULT_ADMIN_PASSWORD": "test-password",
}


def apply_test_environment(
    monkeypatch: pytest.MonkeyPatch,
    overrides: Mapping[str, str] | None = None,
    *,
    preserve_existing: bool = False,
) -> None:
    values = {
        key: os.environ.get(key, value) if preserve_existing else value
        for key, value in DEFAULT_TEST_ENVIRONMENT.items()
    }
    values.update(overrides or {})
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def environment_from_current_process() -> dict[str, str]:
    return {
        key: os.environ[key] for key in DEFAULT_TEST_ENVIRONMENT if key in os.environ
    }
