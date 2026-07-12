from dataclasses import dataclass
from uuid import uuid4

from executor_bot.infrastructure.http import PerformerProfileDTO
from executor_bot.presentation.ui import (
    contact_methods_keyboard,
    executor_profile_text,
    legal_documents_text,
    registration_summary_keyboard,
    select_city_keyboard,
    summary_text,
)
from executor_bot.presentation.ui.keyboards import (
    REGISTRATION_ACCEPT_LEGAL,
    REGISTRATION_CITY_PREFIX,
    REGISTRATION_CONFIRM,
)


@dataclass(frozen=True)
class Document:
    document_type: str
    version: str
    content_url: str


@dataclass(frozen=True)
class City:
    name: str


def test_legal_documents_text_escapes_html() -> None:
    text = legal_documents_text(
        [Document(document_type="Terms <A>", version="v1", content_url="https://x")],
    )

    assert "Terms &lt;A&gt;" in text
    assert "Напишите" not in text


def test_registration_summary_escapes_user_values() -> None:
    text = summary_text(
        {
            "full_name": "Иван <script>",
            "phone": "+7",
            "city_name": "Москва",
            "contact_method_label": "Telegram",
            "about_text": "Опыт <5 лет>",
        },
    )

    assert "Иван &lt;script&gt;" in text
    assert "Опыт &lt;5 лет&gt;" in text


def test_registration_keyboards_are_inline_first() -> None:
    city_keyboard = select_city_keyboard([City("Москва")])
    contact_keyboard = contact_methods_keyboard()
    summary_keyboard = registration_summary_keyboard()

    assert city_keyboard.inline_keyboard[0][0].callback_data == (
        f"{REGISTRATION_CITY_PREFIX}0"
    )
    assert contact_keyboard.inline_keyboard[0][0].callback_data is not None
    assert summary_keyboard.inline_keyboard[0][0].callback_data == REGISTRATION_CONFIRM
    assert REGISTRATION_ACCEPT_LEGAL == "registration:legal:accept"


def test_executor_profile_text_escapes_user_values() -> None:
    text = executor_profile_text(
        PerformerProfileDTO(
            id=uuid4(),
            telegram_id=123,
            full_name="Иван <script>",
            phone="+7",
            telegram_username="name",
            contact_method="telegram",
            city_id=uuid4(),
            about_text="Опыт <5 лет>",
            status="profile_pending",
            is_accepting_orders=False,
        ),
    )

    assert "Иван &lt;script&gt;" in text
    assert "Опыт &lt;5 лет&gt;" in text
