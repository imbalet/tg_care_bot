from customer_bot.presentation.callbacks import CareObjectSkipCallback
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


def test_pet_species_step_can_be_skipped() -> None:
    result = SpeciesScreen().build()

    assert CareObjectSkipCallback().pack() in _callbacks(result.reply_markup)


def test_pet_breed_step_can_be_skipped() -> None:
    result = BreedScreen().build()

    assert CareObjectSkipCallback().pack() in _callbacks(result.reply_markup)


def test_pet_size_step_can_be_skipped() -> None:
    result = SizeScreen().build()

    assert CareObjectSkipCallback().pack() in _callbacks(result.reply_markup)
