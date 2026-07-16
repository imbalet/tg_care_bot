from aiogram.filters.callback_data import CallbackData

from customer_bot.presentation.types import ContactMethod, YesNoValue


class HelpCallback(CallbackData, prefix="help"):
    pass


class CategorySelectCallback(CallbackData, prefix="cat_select"):
    code: str


class CategoryChangeCallback(CallbackData, prefix="cat_change"):
    pass


class ScenarioContinueCallback(CallbackData, prefix="scenario_continue"):
    pass


class ScenarioCancelCallback(CallbackData, prefix="scenario_cancel"):
    pass


class MainMenuCallback(CallbackData, prefix="main_menu"):
    pass


class CloseMessageCallback(CallbackData, prefix="close_msg"):
    pass


class ProfileOpenCallback(CallbackData, prefix="profile_open"):
    pass


class OrdersListCallback(CallbackData, prefix="orders_list"):
    pass


class ServicesPricesCallback(CallbackData, prefix="services_prices"):
    pass


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


class CareObjectsOpenCallback(CallbackData, prefix="care_open"):
    category_code: str | None = None


class CareObjectAddCallback(CallbackData, prefix="care_add"):
    object_type: str


class CareObjectSelectCallback(CallbackData, prefix="care_select"):
    index: int


class CareObjectEditCallback(CallbackData, prefix="care_edit"):
    index: int


class CareObjectDeleteCallback(CallbackData, prefix="care_delete"):
    index: int


class CareObjectDeleteConfirmCallback(CallbackData, prefix="care_delete_ok"):
    index: int


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
    index: int


class AddressDeleteCallback(CallbackData, prefix="addr_delete"):
    index: int


class AddressDeleteConfirmCallback(CallbackData, prefix="addr_delete_ok"):
    index: int


class AddressCityCallback(CallbackData, prefix="addr_city"):
    index: int


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
    index: int


class OrderObjectCallback(CallbackData, prefix="order_object"):
    index: int


class OrderObjectsDoneCallback(CallbackData, prefix="order_objects_done"):
    pass


class OrderAddressCallback(CallbackData, prefix="order_address"):
    index: int


class OrderPhotoConsentCallback(CallbackData, prefix="order_photo"):
    value: YesNoValue


class OrderCommentSkipCallback(CallbackData, prefix="order_comment_skip"):
    pass


class OrderPublishPoolCallback(CallbackData, prefix="order_publish_pool"):
    pass


class OrderPublishDirectCallback(CallbackData, prefix="order_publish_direct"):
    index: int
