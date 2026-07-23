.PHONY: lint check test test-all test-unit test-api test-integration test-e2e test-clean

lint:
	uv run ruff format src alembic tests
	uv run ruff check --fix src alembic tests
	uv run ruff check src alembic tests
	uv run mypy src

check: lint

test:
	uv run pytest -m "unit or api"

test-all:
	uv run ruff format --check src alembic tests
	uv run ruff check src alembic tests
	uv run mypy src tests
	uv run python -m compileall -q src tests
	docker compose -f docker-compose.test.yml config >/dev/null
	uv run pytest -m "unit or api"
	$(MAKE) test-integration
	$(MAKE) test-e2e

test-unit:
	uv run pytest -m unit

test-api:
	uv run pytest -m api

test-integration:
	set -eu; \
	cleanup() { \
		if [ "$${KEEP_TEST_DATABASES:-0}" = "1" ]; then \
			docker compose -f docker-compose.test.yml down --remove-orphans; \
		else \
			docker compose -f docker-compose.test.yml down -v --remove-orphans; \
		fi; \
	}; \
	trap cleanup EXIT INT TERM; \
	docker compose -f docker-compose.test.yml build test-runner mock-external; \
	docker compose -f docker-compose.test.yml up --build -d postgres redis minio mock-external; \
	docker compose -f docker-compose.test.yml run --rm test-runner \
		uv run pytest -m integration -n auto --maxprocesses=15

test-e2e:
	set -e; \
	status=0; \
	cleanup() { docker compose -f docker-compose.test.yml down -v --remove-orphans; }; \
	trap cleanup EXIT INT TERM; \
	docker compose -f docker-compose.test.yml build test-runner e2e-runner mock-external; \
	docker compose -f docker-compose.test.yml up --build -d \
		postgres redis minio mock-external migrate api worker; \
	docker compose -f docker-compose.test.yml up \
		--abort-on-container-exit --exit-code-from e2e-runner e2e-runner || status=$$?; \
	exit $$status

test-clean:
	docker compose -f docker-compose.test.yml down -v --remove-orphans
