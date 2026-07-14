from enum import StrEnum


class ScreenKey(StrEnum):
    MAIN = "main"
    FLOW = "flow"
    ORDER = "order"


class ContactMethod(StrEnum):
    TELEGRAM = "telegram"
    PHONE = "phone"
    BOTH = "both"


class YesNoValue(StrEnum):
    YES = "yes"
    NO = "no"
