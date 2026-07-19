# async def send_step(
#     *,
#     bot: Bot,
#     event: Message | CallbackQuery,
#     telegram_responder: TelegramResponder,
#     telegram_user_context: TelegramUserContext,
#     text: str,
#     reply_markup: ReplyMarkupUnion | None = None,
#     create_new: bool = False,
#     delete_event_message: bool = False,
# ) -> Message | None:
#     return await telegram_responder.update(
#         bot=bot,
#         event=event,
#         telegram_id=telegram_user_context.telegram_id,
#         text=text,
#         reply_markup=reply_markup,
#         create_new=create_new,
#         delete_event_message=delete_event_message,
#     )
