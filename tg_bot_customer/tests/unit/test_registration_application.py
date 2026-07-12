from uuid import uuid4

from customer_bot.application.registration import (
    CONTACT_METHODS,
    format_contact_methods,
    parse_city_choice,
)


def test_parse_city_choice_returns_uuid_by_one_based_index() -> None:
    city_id = uuid4()

    assert parse_city_choice("1", [str(city_id)]) == city_id


def test_parse_city_choice_rejects_bad_input() -> None:
    city_id = uuid4()

    assert parse_city_choice("abc", [str(city_id)]) is None
    assert parse_city_choice("2", [str(city_id)]) is None


def test_contact_methods_are_rendered() -> None:
    text = format_contact_methods()

    assert CONTACT_METHODS["1"][0] == "telegram"
    assert "Telegram" in text
    assert "Телефон" in text
