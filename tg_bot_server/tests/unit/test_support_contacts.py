import pytest

from backend.bootstrap.services.support import SupportServices

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("contact_method", "expected_phone", "expected_telegram"),
    (
        ("phone", "+70000000000", None),
        ("telegram", None, "executor"),
        ("both", "+70000000000", "executor"),
    ),
)
def test_contact_details_expose_only_permitted_channels(
    contact_method: str,
    expected_phone: str | None,
    expected_telegram: str | None,
) -> None:
    result = SupportServices._contact_details(
        contact_method=contact_method,
        full_name="Исполнитель",
        phone="+70000000000",
        telegram_username="executor",
    )

    assert result == ("Исполнитель", expected_phone, expected_telegram)


def test_contact_details_do_not_fallback_to_an_unpermitted_channel() -> None:
    result = SupportServices._contact_details(
        contact_method="telegram",
        full_name="Исполнитель",
        phone="+70000000000",
        telegram_username=None,
    )

    assert result == ("Исполнитель", None, None)
