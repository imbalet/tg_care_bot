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

Run the complete local verification sequence with:

```bash
make test-all
```

`make test-all` enforces the current local coverage baseline of 60% for the
unit/API suite. Raise it explicitly as coverage grows, for example with
`COVERAGE_MIN=70 make test-all`; integration and E2E coverage remain separate
because they execute inside disposable Docker images.

This command checks formatting, linting and typing, then runs unit/API,
PostgreSQL integration and Compose E2E tests. Integration and E2E images are
rebuilt before execution. The test runner image contains the source, tests and
virtual environment; the project directory is never mounted into it.

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

Integration fixtures provide a real PostgreSQL session, Redis client and MinIO
client. Each xdist worker receives a database cloned from the migrated
template, and each test session is rolled back after the test. Redis and S3
resources are cleaned by their fixtures. Shared fake adapters are available in
`tests/support/fakes.py` for clocks, object storage, payments, geocoding and
external HTTP calls.

For focused runs use pytest directly, for example:

```bash
uv run pytest tests/unit/test_test_doubles.py -m unit
docker compose -f docker-compose.test.yml run --rm test-runner \
  uv run pytest tests/integration/test_test_resources.py -m integration -n 1
```

When debugging a failed integration run, use `KEEP_TEST_DATABASES=1` and
inspect the service logs with `docker compose -f docker-compose.test.yml logs`.
Finish with `make test-clean` after debugging.
