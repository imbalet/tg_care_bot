from enum import StrEnum


class MsgKey(StrEnum):
    ACCEPTING_ORDERS = "accepting_orders"
    ADD_ADDRESS = "add_address"
    ALL_CATEGORIES = "all_categories"
    AVATAR = "avatar"
    BACK_TO_LIST = "back_to_list"
    CALENDAR = "calendar"
    CONFIRM = "confirm"
    CURRENT_CATEGORY = "current_category"
    DELETE = "delete"
    EDIT = "edit"
    HELP = "help"
    MAIN_MENU = "main_menu"
    MY_ORDERS = "my_orders"
    PAUSE = "pause"
    PROFILE = "profile"
    SERVICES = "services"
    SKIP = "skip"
    SWITCH_CATEGORY = "switch_category"
    AVAILABLE_ORDERS = "available_orders"
    WORK_ADDRESS = "work_address"


TEXTS: dict[MsgKey, str] = {
    MsgKey.ACCEPTING_ORDERS: "Принимать заказы",
    MsgKey.ADD_ADDRESS: "Добавить адрес",
    MsgKey.ALL_CATEGORIES: "Все направления",
    MsgKey.AVATAR: "Аватар",
    MsgKey.BACK_TO_LIST: "К списку",
    MsgKey.CALENDAR: "Календарь",
    MsgKey.CONFIRM: "Подтвердить",
    MsgKey.CURRENT_CATEGORY: "Текущее направление",
    MsgKey.DELETE: "Удалить",
    MsgKey.EDIT: "Редактировать",
    MsgKey.HELP: "Помощь",
    MsgKey.MAIN_MENU: "Главное меню",
    MsgKey.MY_ORDERS: "Мои заказы",
    MsgKey.PAUSE: "Пауза",
    MsgKey.PROFILE: "Профиль",
    MsgKey.SERVICES: "Услуги",
    MsgKey.SKIP: "Пропустить",
    MsgKey.SWITCH_CATEGORY: "Сменить направление",
    MsgKey.AVAILABLE_ORDERS: "Доступные заказы",
    MsgKey.WORK_ADDRESS: "Рабочий адрес",
}


def text(key: MsgKey) -> str:
    return TEXTS[key]
