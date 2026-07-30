from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

from executor_bot.application.dto import (
    AddressDTO,
    BusyIntervalDTO,
    CalendarDTO,
    PerformerScheduleDTO,
)
from executor_bot.infrastructure.http import PerformerProfileDTO
from executor_bot.presentation.callbacks import WorkAddressSelectCallback
from executor_bot.presentation.handlers.addresses.router import select_address
from executor_bot.presentation.handlers.services_calendar import _calendar_view
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.ui import (
    avatar_keyboard,
    calendar_text,
    cancel_confirmation_keyboard,
    contact_methods_keyboard,
    executor_profile_text,
    executor_setup_hint_text,
    legal_documents_text,
    registration_summary_keyboard,
    report_attachment_keyboard,
    report_skip_keyboard,
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
from executor_bot.presentation.ui.screens.keyboards import (
    my_order_card_keyboard_for_status,
)
from executor_bot.presentation.ui.screens.texts import (
    available_orders_text,
    my_orders_page_text,
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

    address_text = executor_setup_hint_text(("address",))
    assert "добавьте и выберите рабочий адрес" in address_text


def test_calendar_text_describes_unavailability_period_not_exception() -> None:
    text = calendar_text()

    assert "период недоступности" in text
    assert "исключение" not in text


def test_calendar_view_localizes_schedule_and_busy_interval_kinds() -> None:
    calendar = CalendarDTO(
        schedule=PerformerScheduleDTO(
            schedule_type="custom",
            work_days=(1, 3, 5),
            work_start_time="09:00:00",
            work_end_time="18:00:00",
        ),
        overrides=(),
        busy_intervals=(
            BusyIntervalDTO(
                id=uuid4(),
                kind="response",
                status="active",
                starts_at=datetime(2026, 7, 28, 10, 0),
                ends_at=datetime(2026, 7, 28, 11, 0),
            ),
        ),
    )

    text = _calendar_view(calendar)

    assert "пн, ср, пт" in text
    assert "отклик" in text
    assert "custom" not in text
    assert "response" not in text


def test_available_orders_text_shows_distance_or_missing_coordinates() -> None:
    item = type("Order", (), {
        "service_name": "Уход",
        "start_at": "28.07.2026 10:00",
        "end_at": "28.07.2026 11:00",
        "objects_count": 1,
        "total_amount": Decimal("600.00"),
        "distance_km": Decimal("3.125"),
    })()
    text = available_orders_text([item], "all")
    assert "Расстояние: 3.125 км" in text

    item.distance_km = None
    assert "Расстояние: недоступно (нет координат)" in available_orders_text(
        [item], "all"
    )
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


def test_report_skip_is_an_inline_callback_for_each_optional_step() -> None:
    for step in ("comment", "problem_description", "attachment"):
        keyboard = report_skip_keyboard(step)
        button = keyboard.inline_keyboard[0][0]

        assert button.text == "Пропустить"
        assert button.callback_data == f"order_report_skip:{step}"


def test_report_attachment_keyboard_uses_done_after_upload() -> None:
    keyboard = report_attachment_keyboard(has_attachments=True)
    button = keyboard.inline_keyboard[0][0]

    assert button.text == "Готово"
    assert button.callback_data == "order_report_submit"


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


def test_my_orders_page_text_shows_short_order_id() -> None:
    order_id = uuid4()
    item = type(
        "Order",
        (),
        {
            "id": order_id,
            "service_name": "Прогулка",
            "status": "confirmed",
            "start_at": datetime(2026, 7, 28, 10, 0),
            "end_at": datetime(2026, 7, 28, 11, 0),
            "total_amount": "500",
        },
    )()
    page = type(
        "Page",
        (),
        {"items": (item,), "page": 1, "total_pages": 1, "total_items": 1},
    )()

    text = my_orders_page_text(page, "active")

    assert f"ID: #{str(order_id)[:8]}" in text


def test_cancel_confirmation_keyboard_has_confirm_and_back_actions() -> None:
    keyboard = cancel_confirmation_keyboard("12345678-1234-1234-1234-123456789abc")

    assert "order_cancel_confirm" in str(keyboard.inline_keyboard[0][0].callback_data)
    assert "my_order_card" in str(keyboard.inline_keyboard[1][0].callback_data)


def test_in_progress_order_has_no_cancel_action() -> None:
    keyboard = my_order_card_keyboard_for_status(
        status="in_progress",
        order_id="12345678-1234-1234-1234-123456789abc",
        group="active",
        page=1,
    )

    callback_data = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]

    assert not any("order_cancel" in value for value in callback_data)


async def test_work_address_selection_reloads_backend_after_stale_fsm_state() -> None:
    address = AddressDTO(
        id=uuid4(),
        city_id=uuid4(),
        address_text="Ростов-на-Дону, ул. Тестовая, 1",
        entrance=None,
        floor=None,
        apartment=None,
        comment=None,
    )
    backend_client = AsyncMock()
    backend_client.list_work_addresses.return_value = (address,)
    state = AsyncMock()
    state.get_data.return_value = {
        "work_addresses": [
            {
                "id": str(address.id),
                "city_id": str(address.city_id),
                "address_text": address.address_text,
                "entrance": None,
                "floor": None,
                "apartment": None,
                "comment": None,
            },
        ],
    }
    responder = AsyncMock()

    await select_address(
        callback=object(),
        bot=object(),
        state=state,
        backend_client=backend_client,
        telegram_responder=responder,
        telegram_user_context=TelegramUserContext(
            telegram_id=100,
            username=None,
            chat_id=100,
        ),
        callback_data=WorkAddressSelectCallback(index=0),
    )

    backend_client.list_work_addresses.assert_awaited_once_with(telegram_id=100)
    state.update_data.assert_awaited_once()
    update_call = responder.update.await_args.kwargs
    assert address.address_text in update_call["text"]
