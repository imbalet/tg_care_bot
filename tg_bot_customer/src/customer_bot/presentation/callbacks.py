from uuid import UUID

from aiogram.filters.callback_data import CallbackData

from customer_bot.presentation.types import ContactMethod, YesNoValue


class HelpCallback(CallbackData, prefix="help"):
    pass


class SupportOpenCallback(CallbackData, prefix="support_open"):
    pass


class CategorySelectCallback(CallbackData, prefix="cat_select"):
    code: str


class CategoryChangeCallback(CallbackData, prefix="cat_change"):
    pass


class MainMenuCallback(CallbackData, prefix="main_menu"):
    pass


class CloseMessageCallback(CallbackData, prefix="close_msg"):
    pass


class ProfileOpenCallback(CallbackData, prefix="profile_open"):
    pass


class OrdersListCallback(CallbackData, prefix="orders_list"):
    pass


class OrdersPageCallback(CallbackData, prefix="orders_page"):
    group: str = "active"
    page: int = 1
    category_code: str | None = None


class OrderCardOpenCallback(CallbackData, prefix="order_card"):
    order_id: UUID
    group: str = "active"
    page: int = 1
    category_code: str | None = None


class NotificationOrderOpenCallback(CallbackData, prefix="notification_order"):
    order_id: UUID


class OrderResponsesOpenCallback(CallbackData, prefix="order_resp_open"):
    order_id: UUID


class OrderResponseSelectCallback(CallbackData, prefix="order_resp_select"):
    match_id: UUID


class OrderResponseRejectCallback(CallbackData, prefix="order_resp_reject"):
    match_id: UUID


class PaymentRefreshCallback(CallbackData, prefix="payment_refresh"):
    order_id: UUID


class OrderCancelPreviewCallback(CallbackData, prefix="order_cancel_preview"):
    order_id: UUID


class OrderCancelConfirmCallback(CallbackData, prefix="order_cancel_confirm"):
    order_id: UUID


class OrderLocationOpenCallback(CallbackData, prefix="order_location"):
    order_id: UUID


class OrderReportOpenCallback(CallbackData, prefix="order_report"):
    order_id: UUID


class OrderReportConfirmCallback(CallbackData, prefix="order_report_confirm"):
    order_id: UUID


class OrderComplaintOpenCallback(CallbackData, prefix="order_complaint"):
    order_id: UUID


class SupportRequestOpenCallback(CallbackData, prefix="support_request"):
    order_id: UUID | None = None


class ServicesPricesCallback(CallbackData, prefix="services_prices"):
    pass


class RegistrationLegalAcceptCallback(CallbackData, prefix="reg_legal"):
    pass


class RegistrationCityCallback(CallbackData, prefix="reg_city"):
    city_id: UUID


class RegistrationContactCallback(CallbackData, prefix="reg_contact"):
    method: ContactMethod


class RegistrationConfirmCallback(CallbackData, prefix="reg_confirm"):
    pass


class RegistrationEditCallback(CallbackData, prefix="reg_edit"):
    pass


class CareObjectsOpenCallback(CallbackData, prefix="care_open"):
    category_code: str | None = None


class CareObjectAddCallback(CallbackData, prefix="care_add"):
    object_type: str


class CareObjectSelectCallback(CallbackData, prefix="care_select"):
    care_object_id: UUID


class CareObjectEditCallback(CallbackData, prefix="care_edit"):
    care_object_id: UUID


class CareObjectDeleteCallback(CallbackData, prefix="care_delete"):
    care_object_id: UUID


class CareObjectDeleteConfirmCallback(CallbackData, prefix="care_delete_ok"):
    care_object_id: UUID


class CareObjectAgeCallback(CallbackData, prefix="care_age"):
    age_group: str


class CareObjectSizeCallback(CallbackData, prefix="care_size"):
    size: str


class CareObjectMobilityCallback(CallbackData, prefix="care_mobility"):
    value: YesNoValue


class CareObjectSkipCallback(CallbackData, prefix="care_skip"):
    pass


class AddressesOpenCallback(CallbackData, prefix="addr_open"):
    pass


class AddressAddCallback(CallbackData, prefix="addr_add"):
    pass


class AddressSelectCallback(CallbackData, prefix="addr_select"):
    address_id: UUID


class AddressDeleteCallback(CallbackData, prefix="addr_delete"):
    address_id: UUID


class AddressDeleteConfirmCallback(CallbackData, prefix="addr_delete_ok"):
    address_id: UUID


class AddressCityCallback(CallbackData, prefix="addr_city"):
    city_id: UUID


class AddressSuggestionCallback(CallbackData, prefix="addr_suggestion"):
    index: int


class AddressSkipCallback(CallbackData, prefix="addr_skip"):
    pass


class OrderCreateCallback(CallbackData, prefix="order_create"):
    pass


class OrderAddObjectCallback(CallbackData, prefix="order_add_object"):
    pass


class OrderAddAddressCallback(CallbackData, prefix="order_add_address"):
    pass


class OrderServiceCallback(CallbackData, prefix="order_service"):
    service_id: UUID


class OrderObjectCallback(CallbackData, prefix="order_object"):
    care_object_id: UUID


class OrderObjectsDoneCallback(CallbackData, prefix="order_objects_done"):
    pass


class OrderOptionToggleCallback(CallbackData, prefix="order_option"):
    option_id: UUID


class OrderOptionsDoneCallback(CallbackData, prefix="order_options_done"):
    pass


class OrderStartManualCallback(CallbackData, prefix="order_start_manual"):
    mode: str


class OrderStartTimeCallback(CallbackData, prefix="order_start_time"):
    value: str


class OrderAddressCallback(CallbackData, prefix="order_address"):
    address_id: UUID


class OrderPhotoConsentCallback(CallbackData, prefix="order_photo"):
    value: YesNoValue


class OrderCommentSkipCallback(CallbackData, prefix="order_comment_skip"):
    pass


class OrderPublishPoolCallback(CallbackData, prefix="order_publish_pool"):
    pass


class OrderDirectOpenCallback(CallbackData, prefix="order_direct_open"):
    pass


class OrderDirectNextCallback(CallbackData, prefix="order_direct_next"):
    pass


class OrderDirectPreviousCallback(CallbackData, prefix="order_direct_prev"):
    pass


class OrderDirectBackCallback(CallbackData, prefix="order_direct_back"):
    pass


class OrderPublishDirectCallback(CallbackData, prefix="order_publish_direct"):
    performer_id: UUID
