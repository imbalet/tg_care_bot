# tg_bot_customer

Thin Telegram client for customers. Business rules live in `tg_bot_server`; this
bot keeps only Telegram UI/FSM state in Redis and calls backend over HTTP.

## Local Setup

```bash
uv sync --all-groups
cp .env.example .env
```

Set a real `BOT_TOKEN` before polling Telegram.

Run locally:

```bash
uv run python -m customer_bot.main
```

## Checks

```bash
make lint
uv run pytest
```
