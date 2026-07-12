# tg_bot_executor

Thin Telegram client for executors. Business rules live in `tg_bot_server`; this
bot keeps only Telegram UI/FSM state in Redis and calls backend over HTTP.

## Local Setup

```bash
uv sync --all-groups
cp .env.example .env
```

Set a real `BOT_TOKEN` before polling Telegram.

Run locally:

```bash
uv run python -m executor_bot.main
```

## Checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```
