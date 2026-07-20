import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderPublishDirectCallback,
    OrderPublishPoolCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.orders.state import (
    OrderCreation,
    draft,
    item_by_index,
    string_list,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    OrderPublishedScreen,
    RetryLaterScreen,
)

router = Router(name="orders_publish")
logger = logging.getLogger(__name__)


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
    order_draft = draft(data)
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            logger.warning(
                "Pool order publish requested without customer profile",
                extra={"telegram_id": telegram_user_context.telegram_id},
            )
            raise BackendClientError("Customer profile is missing")
        order_request = _order_request(order_draft)
        order = await backend_client.create_order_pool(
            customer_id=profile.id,
            service_id=order_request.service_id,
            start_at=order_request.start_at,
            end_at=order_request.end_at,
            care_object_ids=order_request.care_object_ids,
            address_id=order_request.address_id,
            customer_comment=order_request.customer_comment,
            report_photo_consent=order_request.report_photo_consent,
            option_values=order_request.option_values,
        )
    except BackendValidationError as exc:
        logger.warning(
            "Backend rejected pool order publish",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to publish pool order",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.clear()
    logger.info(
        "Pool order published",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "order_id": str(order.id),
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderPublishedScreen(order).build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
    performer = await item_by_index(state, "order_performers", callback_data.index)
    if performer is None:
        logger.warning(
            "Stale direct order performer callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    data = await state.get_data()
    order_draft = draft(data)
    try:
        profile = await backend_client.get_customer_profile(
            telegram_user_context.telegram_id,
        )
        if profile is None:
            logger.warning(
                "Direct order publish requested without customer profile",
                extra={"telegram_id": telegram_user_context.telegram_id},
            )
            raise BackendClientError("Customer profile is missing")
        order_request = _order_request(order_draft)
        order = await backend_client.create_order_direct(
            customer_id=profile.id,
            service_id=order_request.service_id,
            start_at=order_request.start_at,
            end_at=order_request.end_at,
            care_object_ids=order_request.care_object_ids,
            address_id=order_request.address_id,
            customer_comment=order_request.customer_comment,
            report_photo_consent=order_request.report_photo_consent,
            option_values=order_request.option_values,
            performer_id=UUID(str(performer["performer_id"])),
        )
    except BackendValidationError as exc:
        logger.warning(
            "Backend rejected direct order publish",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to publish direct order",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.clear()
    logger.info(
        "Direct order published",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "order_id": str(order.id),
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := OrderPublishedScreen(order).build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
    option_values: dict[UUID, object]


def _order_request(order_draft: dict[str, object]) -> _OrderRequest:
    consent_value = order_draft.get("report_photo_consent")
    return _OrderRequest(
        service_id=UUID(str(order_draft["service_id"])),
        start_at=datetime.fromisoformat(str(order_draft["start_at"])),
        end_at=datetime.fromisoformat(str(order_draft["end_at"])),
        care_object_ids=tuple(
            UUID(str(item)) for item in string_list(order_draft["care_object_ids"])
        ),
        address_id=UUID(str(order_draft["address_id"]))
        if order_draft.get("address_id")
        else None,
        customer_comment=str(order_draft["customer_comment"])
        if order_draft.get("customer_comment")
        else None,
        report_photo_consent=consent_value if isinstance(consent_value, bool) else None,
        option_values={
            UUID(str(key)): value
            for key, value in _dict(order_draft.get("option_values")).items()
        },
    )


def _dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}
