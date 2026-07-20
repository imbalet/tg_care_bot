from typing import Protocol

CATEGORY_EMOJIS = {
    "child": "👶",
    "ward": "🧓",
    "pet": "🐾",
}


class _Category(Protocol):
    @property
    def code(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def care_object_type(self) -> str: ...
