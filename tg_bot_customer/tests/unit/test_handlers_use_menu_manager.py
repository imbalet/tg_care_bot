from pathlib import Path


def test_handlers_do_not_call_telegram_reply_methods_directly() -> None:
    handlers_dir = Path("src/customer_bot/presentation/handlers")
    forbidden = ("message.answer(", "callback.answer(", ".send_message(")

    offenders: list[str] = []
    for path in handlers_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern in text:
                offenders.append(f"{path}:{pattern}")

    assert offenders == []
