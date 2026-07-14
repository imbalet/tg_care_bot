from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderPublishDirectCallback,
    OrderPublishPoolCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
)
from customer_bot.presentation.handlers.orders.state import (
    draft as _draft,
)
from customer_bot.presentation.handlers.orders.state import (
    item_by_index as _item_by_index,
)
from customer_bot.presentation.handlers.orders.state import (
    string_list as _string_list,
)
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    order_published_text,
    retry_later_text,
)

router = Router(name="orders_publish")


@router.callback_query(OrderCreation.publish, OrderPublishPoolCallback.filter())
async def publish_pool(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = _draft(data)
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        order_request = _order_request(draft)
        order = await backend_client.create_order_pool(
            customer_id=profile.id,
            service_id=order_request.service_id,
            start_at=order_request.start_at,
            end_at=order_request.end_at,
            care_object_ids=order_request.care_object_ids,
            address_id=order_request.address_id,
            customer_comment=order_request.customer_comment,
            report_photo_consent=order_request.report_photo_consent,
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_published_text(order),
    )


@router.callback_query(
    OrderCreation.publish,
    OrderPublishDirectCallback.filter(),
)
async def publish_direct(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderPublishDirectCallback,
) -> None:
    performer = await _item_by_index(state, "order_performers", callback_data.index)
    if performer is None:
        return
    data = await state.get_data()
    draft = _draft(data)
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            raise BackendClientError("Customer profile is missing")
        order_request = _order_request(draft)
        order = await backend_client.create_order_direct(
            customer_id=profile.id,
            service_id=order_request.service_id,
            start_at=order_request.start_at,
            end_at=order_request.end_at,
            care_object_ids=order_request.care_object_ids,
            address_id=order_request.address_id,
            customer_comment=order_request.customer_comment,
            report_photo_consent=order_request.report_photo_consent,
            performer_id=UUID(str(performer["performer_id"])),
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=order_published_text(order),
    )


@dataclass(frozen=True)
class _OrderRequest:
    service_id: UUID
    start_at: datetime
    end_at: datetime
    care_object_ids: tuple[UUID, ...]
    address_id: UUID | None
    customer_comment: str | None
    report_photo_consent: bool | None


def _order_request(draft: dict[str, object]) -> _OrderRequest:
    consent_value = draft.get("report_photo_consent")
    return _OrderRequest(
        service_id=UUID(str(draft["service_id"])),
        start_at=datetime.fromisoformat(str(draft["start_at"])),
        end_at=datetime.fromisoformat(str(draft["end_at"])),
        care_object_ids=tuple(
            UUID(str(item)) for item in _string_list(draft["care_object_ids"])
        ),
        address_id=UUID(str(draft["address_id"])) if draft.get("address_id") else None,
        customer_comment=str(draft["customer_comment"])
        if draft.get("customer_comment")
        else None,
        report_photo_consent=consent_value if isinstance(consent_value, bool) else None,
    )
