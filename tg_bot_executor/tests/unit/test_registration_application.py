from uuid import uuid4

from executor_bot.application.registration import parse_city_choice


def test_parse_city_choice_returns_uuid_by_one_based_index() -> None:
    city_id = uuid4()

    assert parse_city_choice("1", [str(city_id)]) == city_id


def test_parse_city_choice_rejects_bad_input() -> None:
    city_id = uuid4()

    assert parse_city_choice("abc", [str(city_id)]) is None
    assert parse_city_choice("2", [str(city_id)]) is None
