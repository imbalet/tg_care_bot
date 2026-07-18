.PHONY: lint check

lint:
	uv run ruff format src
	uv run ruff check --fix src
	uv run ruff check src
	uv run mypy src

check: lint
