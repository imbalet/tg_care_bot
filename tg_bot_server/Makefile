.PHONY: lint check test test-unit test-api test-integration test-e2e test-clean

lint:
	uv run ruff format src alembic tests
	uv run ruff check --fix src alembic tests
	uv run ruff check src alembic tests
	uv run mypy src

check: lint

test:
	uv run pytest -m "unit or api"

test-unit:
	uv run pytest -m unit

test-api:
	uv run pytest -m api

test-integration:
	set -e; \
	docker compose -f docker-compose.test.yml up -d postgres redis minio mock-external; \
	status=0; \
	docker compose -f docker-compose.test.yml run --rm test-runner \
		uv run pytest -m integration -n auto --maxprocesses=15 || status=$$?; \
	if [ "$${KEEP_TEST_DATABASES:-0}" = "1" ]; then \
		docker compose -f docker-compose.test.yml down; \
	else \
		docker compose -f docker-compose.test.yml down -v; \
	fi; \
	exit $$status

test-e2e:
	set -e; \
	status=0; \
	docker compose -f docker-compose.test.yml up --build -d \
		postgres redis minio mock-external migrate api worker; \
	docker compose -f docker-compose.test.yml up \
		--abort-on-container-exit --exit-code-from e2e-runner e2e-runner || status=$$?; \
	docker compose -f docker-compose.test.yml down -v; \
	exit $$status

test-clean:
	docker compose -f docker-compose.test.yml down -v --remove-orphans
