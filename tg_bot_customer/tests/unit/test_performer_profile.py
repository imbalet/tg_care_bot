from decimal import Decimal
from uuid import uuid4

from customer_bot.application.dto import (
    PerformerProfileDTO,
    PerformerServiceProfileDTO,
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
