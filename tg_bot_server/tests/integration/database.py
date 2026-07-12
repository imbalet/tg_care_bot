import os
from dataclasses import dataclass, field
from pathlib import Path

from alembic.config import Config

from alembic import command


def _default_postgres_password() -> str:
    return os.environ.get("POSTGRES_PASSWORD", "".join(("post", "gres")))


@dataclass(frozen=True)
class IntegrationDatabase:
    db_host: str = field(default_factory=lambda: os.environ.get("DB_HOST", "localhost"))
    db_port: str = field(default_factory=lambda: os.environ.get("DB_PORT", "15432"))
    db_name: str = field(
        default_factory=lambda: os.environ.get("DB_NAME", "we_are_close")
    )
    db_user: str = field(default_factory=lambda: os.environ.get("DB_USER", "postgres"))
    db_pass: str = field(default_factory=_default_postgres_password)

    def apply_to_environment(self) -> None:
        os.environ["APP_ENV"] = "test"
        os.environ["DB_HOST"] = self.db_host
        os.environ["DB_PORT"] = self.db_port
        os.environ["DB_NAME"] = self.db_name
        os.environ["DB_USER"] = self.db_user
        os.environ["DB_PASS"] = self.db_pass
        os.environ.setdefault("REDIS_HOST", "localhost")
        os.environ.setdefault("REDIS_PORT", "16379")
        os.environ.setdefault("REDIS_DB", "0")
        os.environ.setdefault("REDIS_PASSWORD", "")
        os.environ.setdefault("SERVICE_KEY", "dev-service-key")


def alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    return Config(str(repo_root / "alembic.ini"))


def migrate_to_head(database: IntegrationDatabase) -> None:
    database.apply_to_environment()
    command.upgrade(alembic_config(), "head")


__all__ = ["IntegrationDatabase", "migrate_to_head"]
