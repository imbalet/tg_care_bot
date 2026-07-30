from uuid import UUID

from aiogram import Bot
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from customer_bot.application.dto import PerformerProfileDTO
from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.ui.screens import PerformerProfileScreen

from .telegram_responder import TelegramResponder


async def show_performer_profile(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_id: int,
    profile: PerformerProfileDTO,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    back_order_id: UUID | None = None,
    back_group: str = "active",
    back_page: int = 1,
    back_direct: bool = False,
) -> None:
    screen = PerformerProfileScreen(
        profile,
        back_order_id=back_order_id,
        back_group=back_group,
        back_page=back_page,
        back_direct=back_direct,
    ).build()
    if profile.avatar_url:
        try:
            avatar = await backend_client.download_avatar(profile.avatar_url)
        except BackendClientError:
            avatar = b""
        if avatar:
            await telegram_responder.replace_with_photo(
                bot=bot,
                event=event,
                telegram_id=telegram_id,
                photo=BufferedInputFile(avatar, filename="performer-avatar.jpg"),
                caption=screen.text,
                reply_markup=screen.reply_markup,
            )
            return
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
    )
