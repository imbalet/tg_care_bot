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
make test
```

The default test command runs only isolated unit and FastAPI tests. The test
suite is split into explicit levels:

```bash
make test-unit
make test-api
make test-integration
make test-e2e
```

Integration tests use the test Compose stack and real PostgreSQL, Redis and
MinIO. PostgreSQL is migrated with Alembic, then each pytest-xdist worker gets
an isolated database cloned from the migrated template database.

The E2E command runs pytest inside a disposable test-runner container together
with API, worker, PostgreSQL, Redis, MinIO and deterministic mock external
services.

To preserve worker databases after a failed integration run:

```bash
KEEP_TEST_DATABASES=1 make test-integration
```

Use `make test-clean` to remove the test Compose resources. Alembic migrations
create the default admin and seed the MVP catalog data needed for local startup.
