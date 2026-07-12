# tg_bot_server

Backend API, admin surface foundation and worker process for the service.

## Local Setup

```bash
uv sync --all-groups
cp .env.example .env
```

Run API locally:

```bash
uv run python -m backend.main
```

Run worker locally:

```bash
uv run python -m backend.worker.main
```

## Migrations

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
```

Migrations must target PostgreSQL. SQLite is not used for persistence checks.

## Docker Compose

From this repository:

```bash
docker compose up --build
```

This starts PostgreSQL, Redis, MinIO, API and worker. Compose does not use
`env_file`; secrets and names are interpolated from the shell environment or
Docker Compose's default `.env` file. Docker service hosts and internal ports
are defined in `docker-compose.yml`.

Telegram bot services are behind the `bots` profile because real bot tokens are
required:

```bash
docker compose --profile bots up --build
```

Published development ports:

- API: `http://localhost:18000`
- PostgreSQL: `localhost:15432`
- Redis: `localhost:16379`
- MinIO: `http://localhost:19000`
- MinIO console: `http://localhost:19001`

## Checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```
