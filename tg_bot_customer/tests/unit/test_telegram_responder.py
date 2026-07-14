from datetime import UTC, datetime

import pytest
from aiogram.types import Chat, Message

from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import ScreenKey


class FakeMessageStore:
    def __init__(self, value: int | None = None) -> None:
        self.value = value
        self.deleted: list[tuple[int, str]] = []
        self.saved: list[tuple[int, str, int]] = []

    async def get(self, telegram_id: int, screen_key: str) -> int | None:
        return self.value

    async def set(self, telegram_id: int, screen_key: str, message_id: int) -> None:
        self.saved.append((telegram_id, screen_key, message_id))
        self.value = message_id

    async def delete(self, telegram_id: int, screen_key: str) -> None:
        self.deleted.append((telegram_id, screen_key))
        self.value = None


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []
        self.sent: list[dict[str, object]] = []

    async def edit_message_text(self, **kwargs: object) -> None:
        self.edits.append(kwargs)

    async def send_message(self, **kwargs: object) -> Message:
        self.sent.append(kwargs)
        return _message(99)


def _message(message_id: int) -> Message:
    return Message(
        message_id=message_id,
        date=datetime(2026, 1, 1, tzinfo=UTC),
        chat=Chat(id=123, type="private"),
    )


@pytest.mark.asyncio
async def test_telegram_responder_edits_stored_message_and_deletes_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted: list[int] = []

    async def delete(message: Message) -> None:
        deleted.append(message.message_id)

    monkeypatch.setattr(Message, "delete", delete)
    bot = FakeBot()
    store = FakeMessageStore(value=42)
    manager = TelegramResponder(message_store=store)

    await manager.update(
        bot=bot,  # type: ignore[arg-type]
        event=_message(1),
        telegram_id=123,
        screen_key=ScreenKey.MAIN,
        text="hello",
    )

    assert bot.edits == [
        {"chat_id": 123, "message_id": 42, "text": "hello", "reply_markup": None}
    ]
    assert bot.sent == []
    assert deleted == [1]


@pytest.mark.asyncio
async def test_telegram_responder_create_new_keeps_user_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted: list[int] = []

    async def delete(message: Message) -> None:
        deleted.append(message.message_id)

    monkeypatch.setattr(Message, "delete", delete)
    bot = FakeBot()
    store = FakeMessageStore(value=42)
    manager = TelegramResponder(message_store=store)

    sent = await manager.update(
        bot=bot,  # type: ignore[arg-type]
        event=_message(1),
        telegram_id=123,
        screen_key=ScreenKey.ORDER,
        text="next step",
        create_new=True,
        delete_event_message=False,
    )

    assert sent is not None
    assert sent.message_id == 99
    assert bot.edits == []
    assert bot.sent == [{"chat_id": 123, "text": "next step", "reply_markup": None}]
    assert deleted == []
    assert store.saved == [(123, "order", 99)]


@pytest.mark.asyncio
async def test_telegram_responder_can_skip_storing_new_message() -> None:
    bot = FakeBot()
    store = FakeMessageStore()
    manager = TelegramResponder(message_store=store)

    await manager.update(
        bot=bot,  # type: ignore[arg-type]
        event=_message(1),
        telegram_id=123,
        screen_key=ScreenKey.ORDER,
        text="temporary",
        create_new=True,
        delete_event_message=False,
        store_message=False,
    )

    assert store.saved == []
