from pathlib import Path


def test_handlers_do_not_call_telegram_api_directly() -> None:
    handlers_dir = Path("src/executor_bot/presentation/handlers")
    forbidden = (
        "message.answer(",
        "callback.answer(",
        "callback.message.answer(",
        "send_step(",
        "send_screen(",
    )

    offenders: list[str] = []
    for path in handlers_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern in text:
                offenders.append(f"{path}:{pattern}")

    assert offenders == []
