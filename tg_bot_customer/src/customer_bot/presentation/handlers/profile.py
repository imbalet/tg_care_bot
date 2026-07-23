import logging
from dataclasses import replace
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    ProfileDeletionCheckCallback,
    ProfileDeletionConfirmCallback,
    ProfileEditCallback,
    ProfileOpenCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.keyboard_builder import InlineKeyboardFactory
from customer_bot.presentation.ui.screens import (
    FallbackScreen,
    ProfileScreen,
    RetryLaterScreen,
)

router = Router(name="profile")
logger = logging.getLogger(__name__)


class ProfileEditForm(StatesGroup):
    full_name = State()
    phone = State()
    contact_method = State()


@router.callback_query(ProfileEditCallback.filter())
async def profile_edit_callback(
    callback: CallbackQuery,
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
        await callback.answer("Профиль сейчас недоступен", show_alert=True)
        return
    if profile is None:
        await callback.answer("Профиль не найден", show_alert=True)
        return
    await state.set_state(ProfileEditForm.full_name)
    await state.update_data(
        profile_city_id=str(profile.city_id),
        profile_phone=profile.phone,
    )
    await telegram_responder.update(
        bot=callback.bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=f"Введите ФИО\n\nТекущее: {profile.full_name}",
        reply_markup=None,
        create_new=True,
    )
    await callback.answer()


@router.message(ProfileEditForm.full_name)
async def profile_edit_full_name(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Введите ФИО текстом")
        return
    await state.update_data(profile_full_name=message.text.strip())
    await state.set_state(ProfileEditForm.phone)
    await message.answer("Введите телефон")


@router.message(ProfileEditForm.phone)
async def profile_edit_phone(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Введите телефон текстом")
        return
    await state.update_data(profile_phone=message.text.strip())
    await state.set_state(ProfileEditForm.contact_method)
    await message.answer("Введите способ связи: telegram, phone или both")


@router.message(ProfileEditForm.contact_method)
async def profile_edit_contact_method(
    message: Message,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
) -> None:
    method = message.text.strip().lower() if message.text else ""
    if method not in {"telegram", "phone", "both"}:
        await message.answer("Введите telegram, phone или both")
        return
    data = await state.get_data()
    try:
        await backend_client.update_customer_profile(
            telegram_id=telegram_user_context.telegram_id,
            full_name=str(data["profile_full_name"]),
            phone=str(data["profile_phone"]),
            city_id=UUID(str(data["profile_city_id"])),
            contact_method=method,
        )
    except BackendClientError:
        await message.answer("Не удалось обновить профиль")
        await state.clear()
        return
    await state.clear()
    await message.answer("Профиль обновлён")


@router.callback_query(ProfileDeletionCheckCallback.filter())
async def deletion_check_callback(
    callback: CallbackQuery,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        preflight = await backend_client.get_deletion_preflight(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await callback.answer("Не удалось проверить аккаунт", show_alert=True)
        return
    if preflight.blockers:
        blockers = ", ".join(
            f"{item.get('kind', 'обязательство')}: {item.get('status', '')}"
            for item in preflight.blockers[:5]
        )
        await callback.answer(f"Удаление пока недоступно: {blockers}", show_alert=True)
        return
    await callback.message.answer(
        "Активных обязательств нет. Подтвердить запрос на удаление аккаунта?",
        reply_markup=(
            InlineKeyboardFactory()
            .button("Подтвердить удаление", ProfileDeletionConfirmCallback())
            .as_markup()
        ),
    )
    await callback.answer()


@router.callback_query(ProfileDeletionConfirmCallback.filter())
async def deletion_confirm_callback(
    callback: CallbackQuery,
    backend_client: BackendPort,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        await backend_client.create_deletion_request(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await callback.answer("Удаление сейчас недоступно", show_alert=True)
        return
    await callback.answer("Запрос на удаление отправлен")
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)


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
