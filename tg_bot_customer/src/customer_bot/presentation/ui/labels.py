from enum import StrEnum


class MsgKey(StrEnum):
    ADD = "add"
    ADD_ADDRESS = "add_address"
    ADD_CHILD = "add_child"
    ADD_PET = "add_pet"
    ADD_WARD = "add_ward"
    ADDRESS = "address"
    ALLOW = "allow"
    BACK_TO_LIST = "back_to_list"
    CHILDREN = "children"
    CONFIRM = "confirm"
    CREATE_ORDER = "create_order"
    DELETE = "delete"
    DENY = "deny"
    EDIT = "edit"
    EDIT_NAME = "edit_name"
    HELP = "help"
    MAIN_MENU = "main_menu"
    MY_ORDERS = "my_orders"
    PETS = "pets"
    PROFILE = "profile"
    PUBLISH_POOL = "publish_pool"
    SKIP = "skip"
    WARDS = "wards"


TEXTS: dict[MsgKey, str] = {
    MsgKey.ADD: "Добавить",
    MsgKey.ADD_ADDRESS: "Добавить адрес",
    MsgKey.ADD_CHILD: "Добавить ребенка",
    MsgKey.ADD_PET: "Добавить питомца",
    MsgKey.ADD_WARD: "Добавить подопечного",
    MsgKey.ADDRESS: "Адреса",
    MsgKey.ALLOW: "Разрешаю",
    MsgKey.BACK_TO_LIST: "К списку",
    MsgKey.CHILDREN: "Дети",
    MsgKey.CONFIRM: "Подтвердить",
    MsgKey.CREATE_ORDER: "Создать заказ",
    MsgKey.DELETE: "Удалить",
    MsgKey.DENY: "Не разрешаю",
    MsgKey.EDIT: "Редактировать",
    MsgKey.EDIT_NAME: "Редактировать имя",
    MsgKey.HELP: "Помощь",
    MsgKey.MAIN_MENU: "Главное меню",
    MsgKey.MY_ORDERS: "Мои заказы",
    MsgKey.PETS: "Питомцы",
    MsgKey.PROFILE: "Профиль",
    MsgKey.PUBLISH_POOL: "Опубликовать в пул",
    MsgKey.SKIP: "Пропустить",
    MsgKey.WARDS: "Подопечные",
}


def text(key: MsgKey) -> str:
    return TEXTS[key]
