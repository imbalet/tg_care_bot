.PHONY: lint check

lint:
	uv run ruff format .
	uv run ruff check --fix .
	uv run ruff check .
	uv run mypy src tests

check: lint
