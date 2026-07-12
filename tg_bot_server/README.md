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
cp .env.example .env
docker compose up --build
```

This starts PostgreSQL, Redis, MinIO, API and worker. Compose does not use
`env_file`; secrets and names are interpolated from the shell environment or
Docker Compose's default `.env` file. Docker service hosts and internal ports
are defined in `docker-compose.yml`.

For CI or one-off local smoke checks, pass the example values explicitly:

```bash
docker compose --env-file .env.example config
docker compose --env-file .env.example up --build
docker compose --env-file .env.example down
```

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
make lint
uv run pytest
```

PostgreSQL integration tests are opt-in and require the local compose
PostgreSQL/Redis ports:

```bash
RUN_POSTGRES_TESTS=1 uv run pytest tests/integration
```

Alembic migrations create the default admin and seed the MVP catalog data needed
for local startup.
