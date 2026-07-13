import logging
from enum import StrEnum
from pathlib import Path


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


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

    logging.basicConfig(
        level=level.value,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )
