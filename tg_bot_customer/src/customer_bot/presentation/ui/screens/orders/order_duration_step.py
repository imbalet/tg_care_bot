from typing import Protocol

from customer_bot.presentation.ui.screens.screen import (
    BaseScreen,
)


class _View(Protocol):
    @property
    def uses_days(self) -> bool: ...


class Screen(BaseScreen[_View]):
    def _build_text(self) -> str:
        unit = "суток" if self.data.uses_days else "часов"
        return f"<b>Длительность</b>\n\nВведите количество {unit} целым числом."
