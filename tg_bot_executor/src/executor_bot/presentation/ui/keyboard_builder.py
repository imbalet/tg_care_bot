from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .labels import MsgKey, text


class InlineKeyboardFactory:
    def __init__(self, row_width: int = 1) -> None:
        self._rows: list[list[InlineKeyboardButton]] = []
        self._current_row: list[InlineKeyboardButton] = []
        self._row_width = row_width

    def button(
        self,
        label: MsgKey | str,
        callback: CallbackData,
    ) -> InlineKeyboardFactory:
        button_text = text(label) if isinstance(label, MsgKey) else label
        self._current_row.append(
            InlineKeyboardButton(text=button_text, callback_data=callback.pack())
        )
        if len(self._current_row) >= self._row_width:
            self.row()
        return self

    def url_button(self, label: str, url: str) -> InlineKeyboardFactory:
        self._current_row.append(InlineKeyboardButton(text=label, url=url))
        if len(self._current_row) >= self._row_width:
            self.row()
        return self

    def row(self) -> InlineKeyboardFactory:
        if self._current_row:
            self._rows.append(self._current_row)
            self._current_row = []
        return self

    def as_markup(self) -> InlineKeyboardMarkup:
        self.row()
        return InlineKeyboardMarkup(inline_keyboard=self._rows)
