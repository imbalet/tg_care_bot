import logging
import sys

SAFE_EXTRA_FIELDS = (
    "request_id",
    "actor_type",
    "actor_id",
    "order_id",
    "match_id",
    "payment_id",
    "refund_id",
    "notification_id",
    "job_name",
    "operation_name",
    "attempt",
    "max_attempts",
    "delay_seconds",
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


def configure_logging(log_level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        SafeExtraFormatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ),
    )
    logging.basicConfig(
        level=log_level.upper(),
        handlers=[handler],
        force=True,
    )
