from unittest.mock import AsyncMock

import pytest

from customer_bot.presentation.callbacks import CareObjectSkipCallback
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.care_objects.completion import _create_from_draft
from customer_bot.presentation.ui.screens.care_objects.care_object_breed_step import (
    Screen as BreedScreen,
)
from customer_bot.presentation.ui.screens.care_objects.care_object_size_step import (
    Screen as SizeScreen,
)
from customer_bot.presentation.ui.screens.care_objects.care_object_species_step import (
    Screen as SpeciesScreen,
)


def _callbacks(markup: object) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]


def test_pet_species_step_is_required() -> None:
    result = SpeciesScreen().build()

    assert CareObjectSkipCallback().pack() not in _callbacks(result.reply_markup)


def test_pet_breed_step_can_be_skipped() -> None:
    result = BreedScreen().build()

    assert CareObjectSkipCallback().pack() in _callbacks(result.reply_markup)


def test_pet_size_step_is_required() -> None:
    result = SizeScreen().build()

    assert CareObjectSkipCallback().pack() not in _callbacks(result.reply_markup)


@pytest.mark.asyncio
async def test_pet_can_be_created_with_optional_breed_and_notes_omitted() -> None:
    backend = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {}
    responder = AsyncMock()

    await _create_from_draft(
        event=object(),
        bot=object(),
        state=state,
        backend_client=backend,
        telegram_responder=responder,
        telegram_user_context=TelegramUserContext(
            telegram_id=123,
            username=None,
            chat_id=None,
        ),
        draft={
            "object_type": "pet",
            "display_name": "Барсик",
            "age_group": "unknown",
            "species": "cat",
            "pet_size": "unknown",
        },
    )

    backend.create_care_object.assert_awaited_once_with(
        telegram_id=123,
        object_type="pet",
        display_name="Барсик",
        age_group="unknown",
        species="cat",
        breed=None,
        pet_size="unknown",
        mobility_assistance_required=None,
        routine_notes=None,
        behavior_notes=None,
    )
