from dataclasses import dataclass
from uuid import uuid4

from executor_bot.infrastructure.http import PerformerProfileDTO
from executor_bot.presentation.ui import (
    avatar_keyboard,
    contact_methods_keyboard,
    executor_profile_text,
    executor_setup_hint_text,
    legal_documents_text,
    registration_summary_keyboard,
    select_city_keyboard,
    summary_text,
    work_address_card_text,
    work_addresses_keyboard,
)
from executor_bot.presentation.ui.keyboards import (
    AVATAR_UPLOAD,
    REGISTRATION_ACCEPT_LEGAL,
    REGISTRATION_CITY_PREFIX,
    REGISTRATION_CONFIRM,
    WORK_ADDRESS_ADD,
    WORK_ADDRESS_SELECT_PREFIX,
)


@dataclass(frozen=True)
class Document:
    document_type: str
    version: str
    content_url: str


@dataclass(frozen=True)
class City:
    name: str


@dataclass(frozen=True)
class Address:
    address_text: str
    entrance: str | None = None
    floor: str | None = None
    apartment: str | None = None
    comment: str | None = None


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


def test_executor_setup_hint_lists_only_missing_setup_steps() -> None:
    text = executor_setup_hint_text(("schedule", "accepting_orders"))

    assert "выберите рабочие дни" in text
    assert "Начать принимать заказы" in text
    assert "включите хотя бы одну одобренную услугу" not in text


def test_work_addresses_keyboard_is_inline_first() -> None:
    keyboard = work_addresses_keyboard([Address(address_text="Тверская")])

    assert keyboard.inline_keyboard[0][0].callback_data == WORK_ADDRESS_ADD
    assert keyboard.inline_keyboard[1][0].callback_data == (
        f"{WORK_ADDRESS_SELECT_PREFIX}0"
    )


def test_work_address_card_text_escapes_user_values() -> None:
    text = work_address_card_text(Address(address_text="Дом <script>"))

    assert "Дом &lt;script&gt;" in text


def test_avatar_keyboard_is_inline_first() -> None:
    keyboard = avatar_keyboard()

    assert keyboard.inline_keyboard[0][0].callback_data == AVATAR_UPLOAD


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
            current_address_id=None,
        ),
    )

    assert "Иван &lt;script&gt;" in text
    assert "Опыт &lt;5 лет&gt;" in text
