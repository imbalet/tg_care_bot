from typing import Protocol

from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
)


class _View(Protocol):
    @property
    def unit(self) -> str: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        unit = {"days": "суток", "hours": "часов", "minutes": "минут"}.get(
            self.data.unit,
            "минут",
        )
        return f"<b>Длительность</b>\n\nВведите количество {unit} целым числом."
