from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

Markup = InlineKeyboardMarkup | ReplyKeyboardMarkup | None


@dataclass(frozen=True, slots=True)
class ScreenResult:
    text: str
    reply_markup: Markup = None
    parse_mode: str | None = "HTML"


class BaseScreen[T](ABC):
    def __init__(self, data: T) -> None:
        self.data = data

    @abstractmethod
    def _build_text(self) -> str:
        raise NotImplementedError

    def _build_keyboard(self) -> Markup:
        return None

    def build(self) -> ScreenResult:
        return ScreenResult(
            text=self._build_text(),
            reply_markup=self._build_keyboard(),
        )


class BaseScreenNoView(ABC):
    @abstractmethod
    def _build_text(self) -> str:
        raise NotImplementedError

    def _build_keyboard(self) -> Markup:
        return None

    def build(self) -> ScreenResult:
        return ScreenResult(
            text=self._build_text(),
            reply_markup=self._build_keyboard(),
        )
