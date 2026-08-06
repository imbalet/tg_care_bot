from decimal import Decimal
from uuid import uuid4

from customer_bot.application.dto import (
    PerformerProfileDTO,
    PerformerServiceProfileDTO,
)
from customer_bot.presentation.callbacks import (
    OrderCardOpenCallback,
    OrderDirectBackCallback,
    OrderResponsesOpenCallback,
)
from customer_bot.presentation.ui.screens.orders.performer_profile import Screen


def test_performer_profile_localizes_service_price_type() -> None:
    profile = PerformerProfileDTO(
        performer_id=uuid4(),
        full_name="Исполнитель",
        about_text="Опыт работы",
        city_name="Ростов-на-Дону",
        avatar_url=None,
        services=(
            PerformerServiceProfileDTO(
                service_id=uuid4(),
                service_name="Передержка",
                price_type="started_24h",
                base_price=Decimal("1200.00"),
                performer_max_objects=2,
            ),
        ),
    )

    text = Screen(profile).build().text

    assert "за начатые сутки" in text
    assert "started_24h" not in text


def test_performer_profile_has_order_back_button_when_opened_from_order() -> None:
    order_id = uuid4()
    profile = PerformerProfileDTO(
        performer_id=uuid4(),
        full_name="Исполнитель",
        about_text=None,
        city_name="Ростов-на-Дону",
        avatar_url="http://minio:9000/private/avatar.jpg",
        services=(),
    )

    markup = Screen(profile, back_order_id=order_id).build().reply_markup

    assert markup is not None
    callback = markup.inline_keyboard[0][0].callback_data
    assert callback is not None
    assert OrderCardOpenCallback.unpack(callback).order_id == order_id


def test_performer_profile_has_direct_back_button() -> None:
    profile = PerformerProfileDTO(
        performer_id=uuid4(),
        full_name="Исполнитель",
        about_text=None,
        city_name="Ростов-на-Дону",
        avatar_url=None,
        services=(),
    )

    markup = Screen(profile, back_direct=True).build().reply_markup

    assert markup is not None
    callback = markup.inline_keyboard[0][0].callback_data
    assert callback is not None
    assert OrderDirectBackCallback.unpack(callback) is not None


def test_performer_profile_has_responses_back_button() -> None:
    order_id = uuid4()
    profile = PerformerProfileDTO(
        performer_id=uuid4(),
        full_name="Исполнитель",
        about_text=None,
        city_name="Ростов-на-Дону",
        avatar_url=None,
        services=(),
    )

    markup = Screen(profile, back_responses_order_id=order_id).build().reply_markup

    assert markup is not None
    callback = markup.inline_keyboard[0][0].callback_data
    assert callback is not None
    assert OrderResponsesOpenCallback.unpack(callback).order_id == order_id
