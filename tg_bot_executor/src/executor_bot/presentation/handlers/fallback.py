from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from executor_bot.application.errors import BackendClientError
from executor_bot.application.ports import ActiveCategoryStore, BackendPort
from executor_bot.presentation.callbacks import (
    HelpCallback,
    MainMenuCallback,
    ProfileDeletionCheckCallback,
    ProfileDeletionConfirmCallback,
    ProfileEditCallback,
    ProfileOpenCallback,
    RegistrationContactCallback,
    SupportOpenCallback,
)
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.navigation import (
    active_category,
    show_category_menu,
    show_category_select,
)
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    contact_methods_keyboard,
    executor_profile_text,
    fallback_keyboard,
    fallback_text,
    help_text,
    invalid_phone_contact_text,
    phone_contact_keyboard,
    phone_step_text,
    select_contact_method_text,
    stale_action_keyboard,
    stale_action_text,
    support_keyboard,
    support_text,
    unavailable_action_text,
)
from executor_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from executor_bot.presentation.ui.screens.labels import MsgKey

router = Router(name="fallback")


class ProfileEditForm(StatesGroup):
    phone = State()
    contact_method = State()


@router.callback_query(ProfileEditCallback.filter())
async def profile_edit_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(ProfileEditForm.phone)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=phone_step_text(),
        reply_markup=phone_contact_keyboard(),
    )


@router.message(ProfileEditForm.phone)
async def profile_edit_phone(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    contact = message.contact
    if contact is None or contact.user_id != telegram_user_context.telegram_id:
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=invalid_phone_contact_text(),
            reply_markup=phone_contact_keyboard(),
            create_new=True,
        )
        return
    await state.update_data(profile_phone=contact.phone_number)
    await state.set_state(ProfileEditForm.contact_method)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text="Телефон получен.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=select_contact_method_text(),
        reply_markup=contact_methods_keyboard(),
        create_new=True,
    )


@router.callback_query(
    ProfileEditForm.contact_method,
    RegistrationContactCallback.filter(),
)
async def profile_edit_contact_method(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: RegistrationContactCallback,
) -> None:
    data = await state.get_data()
    try:
        await backend_client.update_performer_profile(
            telegram_id=telegram_user_context.telegram_id,
            phone=str(data["profile_phone"]),
            contact_method=callback_data.method.value,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=unavailable_action_text(),
            reply_markup=fallback_keyboard(),
        )
        await state.clear()
        return
    await state.clear()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="Профиль обновлён",
        reply_markup=fallback_keyboard(),
    )


@router.callback_query(ProfileDeletionCheckCallback.filter())
async def deletion_check_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
) -> None:
    try:
        preflight = await backend_client.get_deletion_preflight(
            telegram_id=callback.from_user.id,
        )
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Не удалось проверить аккаунт", show_alert=True
        )
        return
    if preflight.blockers:
        await telegram_responder.acknowledge(
            callback,
            "Удаление пока недоступно: есть активные обязательства",
            show_alert=True,
        )
        return
    if not isinstance(callback.message, Message):
        await telegram_responder.acknowledge(
            callback, "Сообщение недоступно", show_alert=True
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=callback.from_user.id,
        text="Активных обязательств нет. Подтвердить удаление аккаунта?",
        reply_markup=InlineKeyboardFactory()
        .button("Подтвердить удаление", ProfileDeletionConfirmCallback())
        .as_markup(),
        create_new=True,
    )


@router.callback_query(ProfileDeletionConfirmCallback.filter())
async def deletion_confirm_callback(
    callback: CallbackQuery,
    telegram_responder: TelegramResponder,
    backend_client: BackendPort,
) -> None:
    try:
        await backend_client.create_deletion_request(telegram_id=callback.from_user.id)
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Удаление сейчас недоступно", show_alert=True
        )
        return
    await telegram_responder.acknowledge(callback, "Запрос на удаление отправлен")


@router.callback_query(MainMenuCallback.filter())
async def main_menu_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await telegram_responder.acknowledge(
            callback, "Сообщение недоступно", show_alert=True
        )
        return
    try:
        registration_state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=unavailable_action_text(),
            reply_markup=fallback_keyboard(),
        )
        return
    if registration_state.state != "registered":
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=help_text(),
            reply_markup=fallback_keyboard(include_main_menu=False),
        )
        return
    category = await active_category(
        backend_client=backend_client,
        active_category_store=active_category_store,
        telegram_id=telegram_user_context.telegram_id,
    )
    if category is None:
        await show_category_select(
            bot=bot,
            event=callback,
            telegram_user_context=telegram_user_context,
            backend_client=backend_client,
            telegram_responder=telegram_responder,
        )
        return
    await show_category_menu(
        bot=bot,
        event=callback,
        telegram_user_context=telegram_user_context,
        telegram_responder=telegram_responder,
        category=category,
    )


@router.callback_query(HelpCallback.filter())
async def help_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if isinstance(message, Message):
        try:
            documents = await backend_client.list_active_legal_documents()
        except BackendClientError:
            documents = ()
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=help_text(),
            reply_markup=fallback_keyboard(
                include_main_menu=True,
                legal_documents=documents,
            ),
        )
        return
    await telegram_responder.acknowledge(
        callback, "Сообщение недоступно", show_alert=True
    )


@router.callback_query(SupportOpenCallback.filter())
async def support_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        contact = await backend_client.get_support_contact()
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=stale_action_text(),
            reply_markup=stale_action_keyboard(),
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=support_text(label=contact.label, telegram_url=contact.telegram_url),
        reply_markup=support_keyboard(
            label=contact.label,
            telegram_url=contact.telegram_url,
        ),
    )


@router.callback_query(ProfileOpenCallback.filter())
async def profile_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    message = callback.message
    if not isinstance(message, Message):
        await telegram_responder.acknowledge(
            callback, "Сообщение недоступно", show_alert=True
        )
        return
    try:
        state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=unavailable_action_text(),
            reply_markup=fallback_keyboard(),
        )
        return
    if state.performer is None:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=fallback_text(),
            reply_markup=fallback_keyboard(),
        )
        return
    cities = await backend_client.list_active_cities()
    city_name = next(
        (city.name for city in cities if city.id == state.performer.city_id),
        str(state.performer.city_id),
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=executor_profile_text(state.performer, city_name=city_name),
        reply_markup=(
            InlineKeyboardFactory()
            .button("Редактировать профиль", ProfileEditCallback())
            .button("Проверить удаление аккаунта", ProfileDeletionCheckCallback())
            .button(MsgKey.MAIN_MENU, MainMenuCallback())
            .as_markup()
        ),
    )


@router.callback_query()
async def unknown_callback(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=stale_action_text(),
        reply_markup=stale_action_keyboard(),
    )


@router.message()
async def unknown_message(
    message: Message,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=fallback_text(),
        reply_markup=fallback_keyboard(),
    )


__all__ = [
    "help_callback",
    "main_menu_callback",
    "profile_callback",
    "router",
    "support_callback",
    "unknown_message",
]
