from dataclasses import dataclass


@dataclass(frozen=True)
class CardScenario:
    name: str
    status: str
    error_code: str
    message: str
    challenge: bool = False


CARD_SCENARIOS: dict[str, CardScenario] = {
    "2201382000000013": CardScenario(
        name="frictionless_success",
        status="AUTHORIZED",
        error_code="0",
        message="",
    ),
    "2201382000000047": CardScenario(
        name="challenge_success",
        status="AUTHORIZED",
        error_code="0",
        message="",
        challenge=True,
    ),
    "2201382000000021": CardScenario(
        name="payment_declined",
        status="REJECTED",
        error_code="1006",
        message="Платеж не прошел",
    ),
    "2201382000000831": CardScenario(
        name="insufficient_funds",
        status="REJECTED",
        error_code="1051",
        message="Недостаточно средств на карте",
    ),
    "2201382000000005": CardScenario(
        name="restricted_3ds",
        status="REJECTED",
        error_code="2015",
        message="Проверка 3DS не пройдена",
    ),
    "2201382000000039": CardScenario(
        name="attempt_success",
        status="AUTHORIZED",
        error_code="0",
        message="",
    ),
    "2200770239097761": CardScenario(
        name="non_3ds_success",
        status="AUTHORIZED",
        error_code="0",
        message="",
    ),
    "2201382000000591": CardScenario(
        name="mock_service_success",
        status="AUTHORIZED",
        error_code="0",
        message="",
    ),
}


def get_scenario(pan: str) -> CardScenario | None:
    return CARD_SCENARIOS.get("".join(character for character in pan if character.isdigit()))
