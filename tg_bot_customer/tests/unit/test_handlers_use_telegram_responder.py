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


def test_customer_bot_does_not_use_removed_navigation_contracts() -> None:
    roots = (Path("src/customer_bot"), Path("tests/unit"))
    forbidden = (
        "MenuManager",
        "menu_manager",
        "topic_key",
        "menu_message",
        "/api/orders/drafts",
        "create_order_draft",
        "publish_order_pool",
        "publish_order_direct",
    )

    offenders: list[str] = []
    current_file = Path(__file__).resolve()
    for root in roots:
        for path in root.rglob("*.py"):
            if path.resolve() == current_file:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                if pattern in text:
                    offenders.append(f"{path}:{pattern}")

    assert offenders == []
