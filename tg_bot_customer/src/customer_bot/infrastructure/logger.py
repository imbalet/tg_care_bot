import logging
from enum import StrEnum
from pathlib import Path


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


SAFE_EXTRA_FIELDS = (
    "telegram_id",
    "chat_id",
    "message_id",
    "update_id",
    "event_type",
    "method",
    "url",
    "status_code",
    "exception_type",
    "screen_key",
    "category_code",
    "object_type",
    "care_object_type",
    "care_object_id",
    "address_id",
    "service_id",
    "order_id",
    "index",
    "performers_count",
)


class SafeExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        extra_parts = [
            f"{field}={value}"
            for field in SAFE_EXTRA_FIELDS
            if (value := getattr(record, field, None)) is not None
        ]
        if not extra_parts:
            return message
        return f"{message} | {' '.join(extra_parts)}"


def setup_logger(
    level: LogLevel = LogLevel.INFO,
    log_dir: Path | None = None,
) -> None:
    """Configure console and optional file logging."""
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
    ]

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.FileHandler(
                log_dir / "app.log",
                encoding="utf-8",
            )
        )

    formatter = SafeExtraFormatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(
        level=level.value,
        handlers=handlers,
        force=True,
    )
