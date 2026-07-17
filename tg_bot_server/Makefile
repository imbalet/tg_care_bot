.PHONY: lint check

lint:
	uv run ruff format src alembic
	uv run ruff check --fix src alembic
	uv run ruff check src alembic
	uv run mypy src

check: lint
