import pytest

from backend.bootstrap.services.support import SupportServices

pytestmark = pytest.mark.unit


def test_contact_details_expose_only_the_selected_channels() -> None:
    details = SupportServices._contact_details(
        contact_method="phone",
        full_name="Иван Иванов",
        phone="+79990000000",
        telegram_username="ivan",
    )
    assert details == ("Иван Иванов", "+79990000000", None)

    details = SupportServices._contact_details(
        contact_method="telegram",
        full_name="Иван Иванов",
        phone="+79990000000",
        telegram_username="ivan",
    )
    assert details == ("Иван Иванов", None, "ivan")

    details = SupportServices._contact_details(
        contact_method="both",
        full_name="Иван Иванов",
        phone="+79990000000",
        telegram_username="ivan",
    )
    assert details == ("Иван Иванов", "+79990000000", "ivan")
