from dataclasses import dataclass
from uuid import uuid4

from customer_bot.infrastructure.http import CustomerProfileDTO
from customer_bot.presentation.ui import (
    care_object_card_text,
    care_objects_keyboard,
    contact_methods_keyboard,
    customer_profile_text,
    legal_documents_text,
    registration_summary_keyboard,
    select_city_keyboard,
    summary_text,
)
from customer_bot.presentation.ui.keyboards import (
    CARE_OBJECT_ADD_PREFIX,
    CARE_OBJECT_SELECT_PREFIX,
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


@dataclass(frozen=True)
class CareObject:
    display_name: str
    object_type: str = "pet"
    age_group: str = "adult"
    species: str | None = "cat"
    breed: str | None = None
    pet_size: str | None = "small"
    mobility_assistance_required: bool | None = None


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
        },
    )

    assert "Иван &lt;script&gt;" in text


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


def test_customer_profile_text_escapes_user_values() -> None:
    text = customer_profile_text(
        CustomerProfileDTO(
            id=uuid4(),
            telegram_id=123,
            full_name="Иван <script>",
            phone="+7",
            telegram_username="name",
            contact_method="telegram",
            city_id=uuid4(),
            status="active",
        ),
    )

    assert "Иван &lt;script&gt;" in text
    assert "@name" in text


def test_care_object_keyboard_is_inline_first() -> None:
    keyboard = care_objects_keyboard([CareObject(display_name="Барсик")])

    assert keyboard.inline_keyboard[0][0].callback_data == (
        f"{CARE_OBJECT_ADD_PREFIX}child"
    )
    assert keyboard.inline_keyboard[3][0].callback_data == (
        f"{CARE_OBJECT_SELECT_PREFIX}0"
    )


def test_care_object_card_text_escapes_user_values() -> None:
    text = care_object_card_text(CareObject(display_name="Барсик <script>"))

    assert "Барсик &lt;script&gt;" in text
