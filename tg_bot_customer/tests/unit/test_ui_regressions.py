from customer_bot.presentation.ui.screens import (
    AddressSuggestionScreen,
    HelpScreen,
    SupportScreen,
)
from customer_bot.presentation.view_models import HelpView


class _Suggestion:
    value = "Москва, ул. Тестовая, 1"


def _labels(markup: object) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def test_address_suggestions_allow_retry() -> None:
    screen = AddressSuggestionScreen((_Suggestion(),)).build()

    assert "Ввести заново" in _labels(screen.reply_markup)


def test_help_screen_does_not_repeat_help_or_broken_support_action() -> None:
    screen = HelpScreen(
        HelpView(
            include_main_menu=True,
            support_label="Аккаунт поддержки",
            support_telegram_url="https://t.me/support",
        )
    ).build()
    labels = _labels(screen.reply_markup)

    assert "Помощь" not in labels
    assert "Связаться с поддержкой" not in labels
    assert "Назад" in labels
    assert "Аккаунт поддержки" in labels
    assert any(
        button.url == "https://t.me/support"
        for row in screen.reply_markup.inline_keyboard
        for button in row
    )


def test_support_screen_keeps_only_telegram_link() -> None:
    screen = SupportScreen(
        type(
            "Support",
            (),
            {"label": "Аккаунт поддержки", "telegram_url": "https://t.me/support"},
        )()
    ).build()
    labels = _labels(screen.reply_markup)

    assert "Написать в поддержку" not in labels
    assert "Главное меню" in labels
    assert any(
        button.url == "https://t.me/support"
        for row in screen.reply_markup.inline_keyboard
        for button in row
    )
