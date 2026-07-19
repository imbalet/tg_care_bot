from aiogram.filters.callback_data import CallbackData

from executor_bot.presentation.types import ContactMethod, OrderFilterScope


class HelpCallback(CallbackData, prefix="help"):
    pass


class SupportOpenCallback(CallbackData, prefix="support_open"):
    pass


class MainMenuCallback(CallbackData, prefix="main_menu"):
    pass


class CategorySelectCallback(CallbackData, prefix="cat_select"):
    code: str


class CategoryChangeCallback(CallbackData, prefix="cat_change"):
    pass


class ProfileOpenCallback(CallbackData, prefix="profile_open"):
    pass


class AvailableOrdersOpenCallback(CallbackData, prefix="orders_feed"):
    scope: OrderFilterScope = OrderFilterScope.CURRENT_CATEGORY


class ExecutorOrdersOpenCallback(CallbackData, prefix="orders_list"):
    scope: OrderFilterScope = OrderFilterScope.CURRENT_CATEGORY


class ExecutorOrdersPageCallback(CallbackData, prefix="my_orders_page"):
    group: str = "active"
    page: int = 1


class ExecutorOrderCardCallback(CallbackData, prefix="my_order_card"):
    order_id: str
    group: str = "active"
    page: int = 1


class PoolRespondCallback(CallbackData, prefix="pool_resp"):
    order_id: str


class DirectAcceptCallback(CallbackData, prefix="direct_accept"):
    match_id: str


class DirectRejectCallback(CallbackData, prefix="direct_reject"):
    match_id: str


class RegistrationLegalAcceptCallback(CallbackData, prefix="reg_legal"):
    pass


class RegistrationCityCallback(CallbackData, prefix="reg_city"):
    index: int


class RegistrationContactCallback(CallbackData, prefix="reg_contact"):
    method: ContactMethod


class RegistrationConfirmCallback(CallbackData, prefix="reg_confirm"):
    pass


class RegistrationEditCallback(CallbackData, prefix="reg_edit"):
    pass


class WorkAddressesOpenCallback(CallbackData, prefix="work_addr_open"):
    pass


class WorkAddressAddCallback(CallbackData, prefix="work_addr_add"):
    pass


class WorkAddressSelectCallback(CallbackData, prefix="work_addr_select"):
    index: int


class WorkAddressDeleteCallback(CallbackData, prefix="work_addr_delete"):
    index: int


class WorkAddressCurrentCallback(CallbackData, prefix="work_addr_current"):
    index: int


class WorkAddressCityCallback(CallbackData, prefix="work_addr_city"):
    index: int


class WorkAddressSuggestionCallback(CallbackData, prefix="work_addr_suggestion"):
    index: int


class WorkAddressSkipCallback(CallbackData, prefix="work_addr_skip"):
    pass


class AvatarOpenCallback(CallbackData, prefix="avatar_open"):
    pass


class AvatarUploadCallback(CallbackData, prefix="avatar_upload"):
    pass


class AvatarDeleteCallback(CallbackData, prefix="avatar_delete"):
    pass


class ServicesOpenCallback(CallbackData, prefix="services_open"):
    pass


class AcceptingOrdersCallback(CallbackData, prefix="accepting_orders"):
    value: bool


class ServiceToggleCallback(CallbackData, prefix="service_toggle"):
    index: int


class ServiceLimitCallback(CallbackData, prefix="service_limit"):
    index: int


class CalendarOpenCallback(CallbackData, prefix="calendar_open"):
    pass


class CalendarScheduleCallback(CallbackData, prefix="calendar_schedule"):
    schedule_type: str


class CalendarUnavailableTomorrowCallback(
    CallbackData,
    prefix="calendar_unavailable_tomorrow",
):
    pass
