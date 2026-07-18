from enum import StrEnum


class ContactMethod(StrEnum):
    TELEGRAM = "telegram"
    PHONE = "phone"
    BOTH = "both"


class OrderFilterScope(StrEnum):
    CURRENT_CATEGORY = "current_category"
    ALL = "all"
