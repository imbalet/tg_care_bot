from enum import StrEnum


class ContactMethod(StrEnum):
    TELEGRAM = "telegram"
    PHONE = "phone"
    BOTH = "both"


class YesNoValue(StrEnum):
    YES = "yes"
    NO = "no"
