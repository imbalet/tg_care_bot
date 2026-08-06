from types import SimpleNamespace

from customer_bot.presentation.ui.screens.profile.profile import Screen


def test_customer_profile_uses_delete_account_label() -> None:
    markup = Screen(
        SimpleNamespace(
            full_name="Заказчик",
            phone="+79990000000",
            telegram_username=None,
            contact_method="phone",
            city_id="city",
            city_name="Ростов-на-Дону",
            status="active",
        )
    ).build().reply_markup

    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "Удалить аккаунт" in labels
    assert "Проверить удаление аккаунта" not in labels
