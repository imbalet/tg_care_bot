from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import asyncpg

from tests.support.settings import DEFAULT_TEST_ENVIRONMENT

_DATABASE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _identifier(value: str) -> str:
    if not _DATABASE_NAME_RE.fullmatch(value):
        raise ValueError(f"Invalid PostgreSQL identifier: {value!r}")
    return f'"{value}"'


def _run_id() -> str:
    value = os.environ.get("PYTEST_XDIST_TESTRUNUID") or os.environ.get(
        "TEST_RUN_ID",
        "local",
    )
    return re.sub(r"[^a-zA-Z0-9_]", "", value)[-20:] or "local"


@dataclass
class IntegrationDatabase:
    worker_id: str
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "127.0.0.1"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "15432")))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    db_password: str = field(
        default_factory=lambda: os.getenv("DB_PASS", "postgres"),
    )
    admin_database: str = field(
        default_factory=lambda: os.getenv("TEST_ADMIN_DATABASE", "postgres"),
    )
    name_prefix: str = field(
        default_factory=lambda: os.getenv("TEST_DATABASE_PREFIX", "we_are_close"),
    )

    def __post_init__(self) -> None:
        token = _run_id()
        self.template_name = self._name("template", token)
        self.database_name = self._name("db", token, self.worker_id)
        self._root = Path(__file__).resolve().parents[3]

    def setup(self) -> None:
        for key, value in DEFAULT_TEST_ENVIRONMENT.items():
            os.environ.setdefault(key, value)
        asyncio.run(self._ensure_template())
        asyncio.run(self._create_worker_database())
        self.apply_environment(self.database_name)

    def cleanup(self) -> None:
        if os.getenv("KEEP_TEST_DATABASES") == "1":
            return
        asyncio.run(self._drop_database(self.database_name))
        asyncio.run(self._drop_template_if_last_worker())

    def apply_environment(self, database_name: str) -> None:
        os.environ.update(
            {
                "APP_ENV": "test",
                "DB_HOST": self.db_host,
                "DB_PORT": str(self.db_port),
                "DB_NAME": database_name,
                "DB_USER": self.db_user,
                "DB_PASS": self.db_password,
            },
        )

    def _name(self, *parts: str) -> str:
        value = "_".join((self.name_prefix, *parts))
        return re.sub(r"[^a-zA-Z0-9_]", "_", value)[:63]

    async def _connect_admin(self) -> asyncpg.Connection:
        return await asyncpg.connect(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_password,
            database=self.admin_database,
        )

    async def _ensure_template(self) -> None:
        connection = await self._connect_admin()
        try:
            await connection.execute(
                "SELECT pg_advisory_lock(hashtext($1))",
                f"pytest:{self.template_name}",
            )
            exists = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = $1)",
                self.template_name,
            )
            if not exists:
                await connection.execute(
                    f"CREATE DATABASE {_identifier(self.template_name)}",
                )
                environment = dict(os.environ)
                try:
                    self.apply_environment(self.template_name)
                    subprocess.run(
                        [sys.executable, "-m", "alembic", "upgrade", "head"],
                        cwd=self._root,
                        env=os.environ.copy(),
                        check=True,
                    )
                finally:
                    os.environ.clear()
                    os.environ.update(environment)
            await connection.execute(
                "SELECT pg_advisory_unlock(hashtext($1))",
                f"pytest:{self.template_name}",
            )
        finally:
            await connection.close()

    async def _create_worker_database(self) -> None:
        connection = await self._connect_admin()
        try:
            exists = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = $1)",
                self.database_name,
            )
            if not exists:
                await connection.execute(
                    "CREATE DATABASE "
                    f"{_identifier(self.database_name)} "
                    f"TEMPLATE {_identifier(self.template_name)}",
                )
        finally:
            await connection.close()

    async def _drop_database(self, database_name: str) -> None:
        connection = await self._connect_admin()
        try:
            await connection.execute(
                f"DROP DATABASE IF EXISTS {_identifier(database_name)} WITH (FORCE)",
            )
        finally:
            await connection.close()

    async def _drop_template_if_last_worker(self) -> None:
        connection = await self._connect_admin()
        try:
            await connection.execute(
                "SELECT pg_advisory_lock(hashtext($1))",
                f"pytest:cleanup:{self.template_name}",
            )
            remaining = await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_database
                    WHERE datname LIKE $1
                )
                """,
                f"{self.name_prefix}_db_{_run_id()}_%",
            )
            if not remaining:
                await connection.execute(
                    "DROP DATABASE IF EXISTS "
                    f"{_identifier(self.template_name)} WITH (FORCE)",
                )
            await connection.execute(
                "SELECT pg_advisory_unlock(hashtext($1))",
                f"pytest:cleanup:{self.template_name}",
            )
        finally:
            await connection.close()
