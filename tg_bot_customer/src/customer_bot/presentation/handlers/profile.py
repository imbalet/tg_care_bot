import logging
from dataclasses import replace

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    MainMenuCallback,
    ProfileDeletionCheckCallback,
    ProfileDeletionConfirmCallback,
    ProfileEditCallback,
    ProfileOpenCallback,
    RegistrationContactCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens import (
    FallbackScreen,
    ProfileScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.ui.screens.registration.phone_step import (
    Screen as PhoneStepScreen,
)
from customer_bot.presentation.ui.screens.registration.select_contact_method import (
    Screen as SelectContactMethodScreen,
)

router = Router(name="profile")
logger = logging.getLogger(__name__)


class ProfileEditForm(StatesGroup):
    phone = State()
    contact_method = State()


@router.callback_query(ProfileEditCallback.filter())
async def profile_edit_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Профиль сейчас недоступен", show_alert=True
        )
        return
    if profile is None:
        await telegram_responder.acknowledge(
            callback, "Профиль не найден", show_alert=True
        )
        return
    await state.set_state(ProfileEditForm.phone)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := PhoneStepScreen()).build().text,
        reply_markup=screen.reply_markup,
    )
    await telegram_responder.acknowledge(callback)


@router.message(ProfileEditForm.phone)
async def profile_edit_phone(
    message: Message,
    state: FSMContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    contact = message.contact
    if contact is None or contact.user_id != telegram_user_context.telegram_id:
        screen = PhoneStepScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                f"{screen.text}\n\n"
                "Можно передать только свой контакт."
            ),
            reply_markup=screen.reply_markup,
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
        create_new=True,
    )
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := SelectContactMethodScreen()).build().text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(
    ProfileEditForm.contact_method,
    RegistrationContactCallback.filter(),
)
async def profile_edit_contact_method(
    callback: CallbackQuery,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
    callback_data: RegistrationContactCallback,
) -> None:
    data = await state.get_data()
    try:
        await backend_client.update_customer_profile(
            telegram_id=telegram_user_context.telegram_id,
            phone=str(data["profile_phone"]),
            contact_method=callback_data.method,
        )
    except BackendClientError:
        await _prompt_profile(
            callback,
            bot,
            telegram_responder,
            telegram_user_context,
            "Не удалось обновить профиль",
        )
        await state.clear()
        return
    await state.clear()
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="Профиль обновлён",
        reply_markup=(
            InlineKeyboardFactory()
            .button("Главное меню", MainMenuCallback())
            .as_markup()
        ),
    )


@router.callback_query(ProfileDeletionCheckCallback.filter())
async def deletion_check_callback(
    callback: CallbackQuery,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
    bot: Bot,
    telegram_responder: TelegramResponder,
) -> None:
    try:
        preflight = await backend_client.get_deletion_preflight(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Не удалось проверить аккаунт", show_alert=True
        )
        return
    if preflight.blockers:
        blockers = ", ".join(
            f"{item.get('kind', 'обязательство')}: {item.get('status', '')}"
            for item in preflight.blockers[:5]
        )
        await telegram_responder.acknowledge(
            callback, f"Удаление пока недоступно: {blockers}", show_alert=True
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text="Активных обязательств нет. Подтвердить запрос на удаление аккаунта?",
        reply_markup=InlineKeyboardFactory()
        .button("Подтвердить удаление", ProfileDeletionConfirmCallback())
        .as_markup(),
    )


@router.callback_query(ProfileDeletionConfirmCallback.filter())
async def deletion_confirm_callback(
    callback: CallbackQuery,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
    telegram_responder: TelegramResponder,
) -> None:
    try:
        await backend_client.create_deletion_request(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await telegram_responder.acknowledge(
            callback, "Удаление сейчас недоступно", show_alert=True
        )
        return
    await telegram_responder.acknowledge(callback, "Запрос на удаление отправлен")
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)


async def _prompt_profile(
    message: Message | CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    text: str,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=None,
        create_new=True,
    )


async def _show_unavailable(
    *,
    bot: Bot,
    event: CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := RetryLaterScreen().build()).text,
        reply_markup=screen.reply_markup,
    )


@router.callback_query(ProfileOpenCallback.filter())
async def profile_callback(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to open customer profile",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
        )
        return
    if profile is None:
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := FallbackScreen().build()).text,
            reply_markup=screen.reply_markup,
        )
        return
    try:
        cities = await backend_client.list_active_cities()
    except BackendClientError as exc:
        logger.warning(
            "Failed to load city for customer profile",
            extra={"exception_type": type(exc).__name__},
        )
        await _show_unavailable(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
        )
        return
    city_name = next(
        (city.name for city in cities if city.id == profile.city_id),
        str(profile.city_id),
    )
    profile_view = replace(profile, city_name=city_name)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := ProfileScreen(profile_view).build()).text,
        reply_markup=screen.reply_markup,
    )


__all__ = ["router"]
