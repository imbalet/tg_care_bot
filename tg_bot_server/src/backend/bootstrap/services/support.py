from dataclasses import dataclass

from sqlalchemy import exists, select

from backend.common.application import new_uuid
from backend.modules.addresses.infrastructure import AddressModel
from backend.modules.files.infrastructure.persistence.models import (
    FileLinkModel,
    FileModel,
)
from backend.modules.orders.infrastructure.exports import OrderModel
from backend.modules.payments.infrastructure import PaymentModel

from ._shared import (
    UUID,
    AccountDeletionRequestModel,
    Any,
    AuthorizationError,
    ComplaintModel,
    ConflictError,
    ContactRequestModel,
    CustomerModel,
    DisputeModel,
    NotificationModel,
    PerformerModel,
    SqlAlchemyAdminAuditRepository,
    SqlAlchemySupportRepository,
    SupportRequestModel,
    ValidationError,
    cast,
    timedelta,
    utc_now,
)
from .context import Service


@dataclass(frozen=True)
class ContactRequestResult:
    record: ContactRequestModel
    contact_name: str
    contact_phone: str | None
    contact_telegram_username: str | None


@dataclass(frozen=True)
class ContactDetailsResult:
    contact_name: str
    contact_phone: str | None
    contact_telegram_username: str | None


class SupportServices(Service):
    @staticmethod
    def _contact_details(
        *,
        contact_method: str,
        full_name: str,
        phone: str,
        telegram_username: str | None,
    ) -> tuple[str, str | None, str | None]:
        return (
            full_name,
            phone if contact_method in {"phone", "both"} else None,
            telegram_username if contact_method in {"telegram", "both"} else None,
        )

    async def _ensure_contact_notification(
        self,
        *,
        session: Any,
        record: ContactRequestModel,
        order_id: UUID,
        recipient_type: str,
        customer_id: UUID | None = None,
        performer_id: UUID | None = None,
    ) -> None:
        notification_id = new_uuid()
        now = utc_now()
        session.add(
            NotificationModel(
                id=notification_id,
                recipient_type=recipient_type,
                customer_id=customer_id,
                performer_id=performer_id,
                type="contact_request_created",
                entity_type="contact_request",
                entity_id=record.id,
                payload={"order_id": str(order_id)},
                deduplication_key=f"contact-request:{record.id}:{notification_id}",
                scheduled_at=now,
                delete_after=now + timedelta(days=30),
            )
        )

    async def create_dispute(
        self,
        *,
        telegram_id: int,
        order_id: UUID,
        text: str,
        file_ids: list[UUID],
    ) -> DisputeModel:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            actor = await repository.get_actor(
                actor_type="customer",
                telegram_id=telegram_id,
                for_update=True,
            )
            existing = await uow.session.scalar(
                select(DisputeModel).where(
                    DisputeModel.order_id == order_id,
                    DisputeModel.status == "open",
                )
            )
            if existing is not None:
                await uow.commit()
                return existing
            order = await uow.session.scalar(
                select(OrderModel)
                .where(
                    OrderModel.id == order_id,
                    OrderModel.customer_id == actor.id,
                )
                .with_for_update()
            )
            if order is None:
                raise AuthorizationError("Order does not belong to customer")
            if order.status not in {"report_submitted", "completed"}:
                raise ConflictError("Order is not available for dispute")
            if (
                order.confirmation_deadline_at is not None
                and order.confirmation_deadline_at < utc_now()
            ):
                raise ConflictError("Dispute window has expired")
            await repository.validate_files(
                actor_type="customer", actor_id=actor.id, file_ids=file_ids
            )
            record = DisputeModel(
                customer_id=actor.id,
                order_id=order.id,
                text=text,
            )
            uow.session.add(record)
            order.payout_status = "blocked"
            order.payout_block_reason = "customer_dispute"
            await uow.session.flush()
            await repository.add_file_links(
                file_ids=file_ids,
                entity_type="dispute",
                entity_id=record.id,
                purpose="dispute_attachment",
            )
            self._add_admin_panel_notification(
                session=uow.session,
                notification_type="dispute_created",
                entity_type="dispute",
                entity_id=record.id,
                deduplication_key=f"dispute-created:{record.id}",
            )
            await uow.commit()
            return record

    async def create_contact_request(
        self,
        *,
        telegram_id: int,
        order_id: UUID,
    ) -> ContactRequestResult:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            customer = await repository.get_actor(
                actor_type="customer",
                telegram_id=telegram_id,
                for_update=True,
            )
            order = await uow.session.scalar(
                select(OrderModel)
                .where(
                    OrderModel.id == order_id,
                    OrderModel.customer_id == customer.id,
                    OrderModel.selected_performer_id.is_not(None),
                    OrderModel.status.in_(
                        ("confirmed", "in_progress", "report_submitted")
                    ),
                    exists(
                        select(PaymentModel.id).where(
                            PaymentModel.id == OrderModel.active_payment_id,
                            PaymentModel.status == "succeeded",
                        )
                    ),
                )
                .with_for_update()
            )
            if order is None or order.selected_performer_id is None:
                raise ConflictError("Order is not available for contact")
            performer = await uow.session.get(
                PerformerModel,
                order.selected_performer_id,
            )
            if performer is None:
                raise ConflictError("Performer is not available for contact")
            existing = await uow.session.scalar(
                select(ContactRequestModel).where(
                    ContactRequestModel.order_id == order.id,
                    ContactRequestModel.status.in_(("requested", "sent")),
                )
            )
            contact_name, contact_phone, contact_telegram = self._contact_details(
                contact_method=performer.contact_method,
                full_name=performer.full_name,
                phone=performer.phone,
                telegram_username=performer.telegram_username,
            )
            if existing is not None:
                if performer.telegram_id:
                    await self._ensure_contact_notification(
                        session=uow.session,
                        record=existing,
                        order_id=order.id,
                        recipient_type="performer",
                        performer_id=performer.id,
                    )
                await uow.commit()
                return ContactRequestResult(
                    record=existing,
                    contact_name=contact_name,
                    contact_phone=contact_phone,
                    contact_telegram_username=contact_telegram,
                )
            record = ContactRequestModel(
                customer_id=customer.id,
                performer_id=performer.id,
                order_id=order.id,
                requested_method=performer.contact_method,
                status="sent" if performer.telegram_id else "failed",
                failure_reason=(
                    None if performer.telegram_id else "telegram_unavailable"
                ),
            )
            uow.session.add(record)
            await uow.session.flush()
            if performer.telegram_id:
                await self._ensure_contact_notification(
                    session=uow.session,
                    record=record,
                    order_id=order.id,
                    recipient_type="performer",
                    performer_id=performer.id,
                )
            await uow.commit()
            return ContactRequestResult(
                record=record,
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_telegram_username=contact_telegram,
            )

    async def create_performer_contact_request(
        self,
        *,
        telegram_id: int,
        order_id: UUID,
    ) -> ContactRequestResult:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            performer = await repository.get_actor(
                actor_type="performer",
                telegram_id=telegram_id,
                for_update=True,
            )
            order = await uow.session.scalar(
                select(OrderModel)
                .where(
                    OrderModel.id == order_id,
                    OrderModel.selected_performer_id == performer.id,
                    OrderModel.customer_id.is_not(None),
                    OrderModel.status.in_(
                        (
                            "confirmed",
                            "in_progress",
                            "waiting_report",
                            "report_submitted",
                        )
                    ),
                    exists(
                        select(PaymentModel.id).where(
                            PaymentModel.id == OrderModel.active_payment_id,
                            PaymentModel.status == "succeeded",
                        )
                    ),
                )
                .with_for_update()
            )
            if order is None or order.customer_id is None:
                raise ConflictError("Order is not available for contact")
            customer = await uow.session.get(CustomerModel, order.customer_id)
            if customer is None:
                raise ConflictError("Customer is not available for contact")
            existing = await uow.session.scalar(
                select(ContactRequestModel).where(
                    ContactRequestModel.order_id == order.id,
                    ContactRequestModel.status.in_(("requested", "sent")),
                )
            )
            contact_name, contact_phone, contact_telegram = self._contact_details(
                contact_method=customer.contact_method,
                full_name=customer.full_name,
                phone=customer.phone,
                telegram_username=customer.telegram_username,
            )
            if existing is not None:
                if customer.telegram_id:
                    await self._ensure_contact_notification(
                        session=uow.session,
                        record=existing,
                        order_id=order.id,
                        recipient_type="customer",
                        customer_id=customer.id,
                    )
                await uow.commit()
                return ContactRequestResult(
                    record=existing,
                    contact_name=contact_name,
                    contact_phone=contact_phone,
                    contact_telegram_username=contact_telegram,
                )
            record = ContactRequestModel(
                customer_id=customer.id,
                performer_id=performer.id,
                order_id=order.id,
                requested_method=customer.contact_method,
                status="sent" if customer.telegram_id else "failed",
                failure_reason=(
                    None if customer.telegram_id else "telegram_unavailable"
                ),
            )
            uow.session.add(record)
            await uow.session.flush()
            if customer.telegram_id:
                await self._ensure_contact_notification(
                    session=uow.session,
                    record=record,
                    order_id=order.id,
                    recipient_type="customer",
                    customer_id=customer.id,
                )
            await uow.commit()
            return ContactRequestResult(
                record=record,
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_telegram_username=contact_telegram,
            )

    async def get_customer_contacts(
        self,
        *,
        telegram_id: int,
        order_id: UUID,
    ) -> ContactDetailsResult:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            customer = await repository.get_actor(
                actor_type="customer",
                telegram_id=telegram_id,
            )
            order = await uow.session.scalar(
                select(OrderModel).where(
                    OrderModel.id == order_id,
                    OrderModel.customer_id == customer.id,
                    OrderModel.selected_performer_id.is_not(None),
                    OrderModel.status.in_(
                        ("confirmed", "in_progress", "report_submitted")
                    ),
                    exists(
                        select(PaymentModel.id).where(
                            PaymentModel.id == OrderModel.active_payment_id,
                            PaymentModel.status == "succeeded",
                        )
                    ),
                )
            )
            if order is None or order.selected_performer_id is None:
                raise ConflictError("Order is not available for contact")
            performer = await uow.session.get(
                PerformerModel, order.selected_performer_id
            )
            if performer is None:
                raise ConflictError("Performer is not available for contact")
            contact_name, contact_phone, contact_telegram = self._contact_details(
                contact_method=performer.contact_method,
                full_name=performer.full_name,
                phone=performer.phone,
                telegram_username=performer.telegram_username,
            )
            return ContactDetailsResult(
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_telegram_username=contact_telegram,
            )

    async def get_performer_contacts(
        self,
        *,
        telegram_id: int,
        order_id: UUID,
    ) -> ContactDetailsResult:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            performer = await repository.get_actor(
                actor_type="performer",
                telegram_id=telegram_id,
            )
            order = await uow.session.scalar(
                select(OrderModel).where(
                    OrderModel.id == order_id,
                    OrderModel.selected_performer_id == performer.id,
                    OrderModel.customer_id.is_not(None),
                    OrderModel.status.in_(
                        (
                            "confirmed",
                            "in_progress",
                            "waiting_report",
                            "report_submitted",
                        )
                    ),
                    exists(
                        select(PaymentModel.id).where(
                            PaymentModel.id == OrderModel.active_payment_id,
                            PaymentModel.status == "succeeded",
                        )
                    ),
                )
            )
            if order is None or order.customer_id is None:
                raise ConflictError("Order is not available for contact")
            customer = await uow.session.get(CustomerModel, order.customer_id)
            if customer is None:
                raise ConflictError("Customer is not available for contact")
            contact_name, contact_phone, contact_telegram = self._contact_details(
                contact_method=customer.contact_method,
                full_name=customer.full_name,
                phone=customer.phone,
                telegram_username=customer.telegram_username,
            )
            return ContactDetailsResult(
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_telegram_username=contact_telegram,
            )

    async def deletion_preflight(
        self, *, actor_type: str, telegram_id: int
    ) -> list[dict[str, Any]]:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            actor = await repository.get_actor(
                actor_type=actor_type,
                telegram_id=telegram_id,
            )
            return await repository.blockers(
                actor_type=actor_type,
                actor_id=actor.id,
            )

    async def create_support_request(
        self,
        *,
        actor_type: str,
        telegram_id: int,
        order_id: UUID | None,
        request_type: str,
        text: str,
        file_ids: list[UUID],
    ) -> SupportRequestModel:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            actor = await repository.get_actor(
                actor_type=actor_type, telegram_id=telegram_id
            )
            actor_id = actor.id
            await repository.validate_order(
                actor_type=actor_type, actor_id=actor_id, order_id=order_id
            )
            await repository.validate_files(
                actor_type=actor_type, actor_id=actor_id, file_ids=file_ids
            )
            if request_type not in {
                "technical",
                "payment",
                "order",
                "account",
                "other",
            }:
                raise ValidationError("Invalid support request type")
            record = SupportRequestModel(
                customer_id=actor_id if actor_type == "customer" else None,
                performer_id=actor_id if actor_type == "performer" else None,
                order_id=order_id,
                direction=actor_type,
                type=request_type,
                text=text,
            )
            uow.session.add(record)
            await uow.session.flush()
            await repository.add_file_links(
                file_ids=file_ids,
                entity_type="support_request",
                entity_id=record.id,
                purpose="support_attachment",
            )
            self._add_admin_panel_notification(
                session=uow.session,
                notification_type="support_request_created",
                entity_type="support_request",
                entity_id=record.id,
                deduplication_key=f"support-request-created:{record.id}",
            )
            await uow.commit()
            return record

    async def create_complaint(
        self,
        *,
        actor_type: str,
        telegram_id: int,
        order_id: UUID | None,
        category: str,
        text: str,
        file_ids: list[UUID],
    ) -> ComplaintModel:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            actor = await repository.get_actor(
                actor_type=actor_type, telegram_id=telegram_id
            )
            actor_id = actor.id
            await repository.validate_order(
                actor_type=actor_type, actor_id=actor_id, order_id=order_id
            )
            await repository.validate_files(
                actor_type=actor_type, actor_id=actor_id, file_ids=file_ids
            )
            if category not in {
                "order_problem",
                "conditions_mismatch",
                "no_contact",
                "post_completion",
            }:
                raise ValidationError("Invalid complaint category")
            record = ComplaintModel(
                customer_id=actor_id if actor_type == "customer" else None,
                performer_id=actor_id if actor_type == "performer" else None,
                order_id=order_id,
                direction=actor_type,
                category=category,
                text=text,
            )
            uow.session.add(record)
            await uow.session.flush()
            await repository.add_file_links(
                file_ids=file_ids,
                entity_type="complaint",
                entity_id=record.id,
                purpose="complaint_attachment",
            )
            self._add_admin_panel_notification(
                session=uow.session,
                notification_type="complaint_created",
                entity_type="complaint",
                entity_id=record.id,
                deduplication_key=f"complaint-created:{record.id}",
            )
            await uow.commit()
            return record

    async def create_deletion_request(
        self, *, actor_type: str, telegram_id: int
    ) -> AccountDeletionRequestModel:
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            actor = await repository.get_actor(
                actor_type=actor_type, telegram_id=telegram_id, for_update=True
            )
            actor_id = actor.id
            existing = await repository.active_deletion(
                actor_type=actor_type, actor_id=actor_id
            )
            if existing is not None:
                await uow.commit()
                return existing
            blockers = await repository.blockers(
                actor_type=actor_type, actor_id=actor_id
            )
            if blockers:
                raise ConflictError(
                    "Account cannot be deleted while obligations are active",
                    details={"blockers": blockers},
                )
            actor.status = "deletion_pending"
            record = AccountDeletionRequestModel(
                customer_id=actor_id if actor_type == "customer" else None,
                performer_id=actor_id if actor_type == "performer" else None,
                blockers=[],
            )
            uow.session.add(record)
            await uow.session.flush()
            self._add_admin_panel_notification(
                session=uow.session,
                notification_type="account_deletion_requested",
                entity_type="account_deletion_request",
                entity_id=record.id,
                deduplication_key=f"account-deletion-requested:{record.id}",
            )
            await uow.commit()
            return record

    async def list_support_records(
        self,
        *,
        actor_type: str,
        telegram_id: int,
        record_kind: str,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Any], int]:
        model = self._support_model(record_kind)
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            actor = await repository.get_actor(
                actor_type=actor_type, telegram_id=telegram_id
            )
            condition = (
                model.customer_id == actor.id
                if actor_type == "customer"
                else model.performer_id == actor.id
            )
            return await repository.list_records_for_actor(
                model=model,
                condition=condition,
                status=status,
                offset=(page - 1) * page_size,
                limit=page_size,
            )

    async def get_support_record(
        self,
        *,
        record_kind: str,
        record_id: UUID,
        actor_type: str | None = None,
        telegram_id: int | None = None,
    ) -> tuple[Any, list[dict[str, Any]]]:
        model = self._support_model(record_kind)
        async with self._uow() as uow:
            repository = SqlAlchemySupportRepository(uow.session)
            record = await repository.get_record(model=model, record_id=record_id)
            if actor_type is not None and telegram_id is not None:
                actor = await repository.get_actor(
                    actor_type=actor_type, telegram_id=telegram_id
                )
                owner_id = (
                    record.customer_id
                    if actor_type == "customer"
                    else record.performer_id
                )
                if owner_id != actor.id:
                    raise AuthorizationError(
                        "Support record belongs to another account"
                    )
            links = await repository.links_for_owner(
                entity_type="support_request"
                if record_kind == "support"
                else record_kind,
                entity_id=record.id,
            )
            files = [
                {
                    "id": file.id,
                    "name": file.original_name,
                    "mime_type": file.mime_type,
                    "size_bytes": file.size_bytes,
                    "url": await self._storage().create_download_url(file.storage_key)
                    if file.storage_key
                    else None,
                }
                for file, _link in links
            ]
            return record, files

    async def list_admin_support_records(
        self, *, record_kind: str, status: str | None, page: int, page_size: int
    ) -> tuple[list[Any], int]:
        async with self._uow() as uow:
            return await SqlAlchemySupportRepository(uow.session).list_records(
                model=self._support_model(record_kind),
                status=status,
                offset=(page - 1) * page_size,
                limit=page_size,
            )

    async def update_support_record(
        self,
        *,
        record_kind: str,
        record_id: UUID,
        status: str,
        admin_comment: str | None,
        admin_id: UUID,
    ) -> Any:
        allowed_statuses = {
            "support": {"open", "in_progress", "waiting_user", "resolved", "closed"},
            "complaint": {
                "open",
                "in_progress",
                "waiting_user",
                "resolved",
                "closed",
                "rejected",
            },
            "dispute": {"open", "in_progress", "waiting_user", "closed"},
            "deletion": {"open", "in_progress", "resolved", "rejected"},
        }
        if status not in allowed_statuses.get(record_kind, set()):
            raise ValidationError("Support status transition is invalid")
        async with self._uow() as uow:
            record = await SqlAlchemySupportRepository(uow.session).update_record(
                model=self._support_model(record_kind),
                record_id=record_id,
                status=status,
                admin_comment=admin_comment,
            )
            if isinstance(record, AccountDeletionRequestModel):
                actor = record.customer_id or record.performer_id
                model = (
                    CustomerModel if record.customer_id is not None else PerformerModel
                )
                account = cast(Any, await uow.session.get(model, actor))
                if account is not None:
                    account.status = (
                        "active" if status == "rejected" else "deletion_pending"
                    )
            if isinstance(record, DisputeModel) and status == "closed":
                order = await uow.session.scalar(
                    select(OrderModel)
                    .where(OrderModel.id == record.order_id)
                    .with_for_update()
                )
                open_dispute = await uow.session.scalar(
                    select(DisputeModel.id).where(
                        DisputeModel.order_id == record.order_id,
                        DisputeModel.status.in_(("open", "in_progress")),
                    )
                )
                if order is not None and open_dispute is None:
                    order.payout_status = "ready"
                    order.payout_block_reason = None
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="update_support_record",
                entity_type=record_kind,
                entity_id=record_id,
                audit_metadata={"status": status, "admin_comment": admin_comment},
            )
            await uow.commit()
            return record

    async def resolve_deletion_request(
        self,
        *,
        record_id: UUID,
        admin_comment: str,
        admin_id: UUID,
    ) -> Any:
        return await self.update_support_record(
            record_kind="deletion",
            record_id=record_id,
            status="resolved",
            admin_comment=admin_comment,
            admin_id=admin_id,
        )

    async def anonymize_deletion_request(
        self,
        *,
        record_id: UUID,
        admin_comment: str,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            record = await uow.session.get(
                AccountDeletionRequestModel, record_id, with_for_update=True
            )
            if record is None:
                raise ValidationError("Deletion request not found")
            actor_type = "customer" if record.customer_id is not None else "performer"
            actor_id = record.customer_id or record.performer_id
            if actor_id is None:
                raise ValidationError("Deletion request owner is missing")
            repository = SqlAlchemySupportRepository(uow.session)
            blockers = await repository.blockers(
                actor_type=actor_type,
                actor_id=actor_id,
            )
            if blockers:
                raise ConflictError(
                    "Account still has blocking obligations",
                    details={"blockers": blockers},
                )
            model = CustomerModel if actor_type == "customer" else PerformerModel
            actor = cast(
                Any,
                await uow.session.get(model, actor_id, with_for_update=True),
            )
            if actor is None:
                raise ValidationError("Deletion request owner not found")
            anonymous_telegram_id = -int(actor_id.hex[:17])
            actor.telegram_id = anonymous_telegram_id
            actor.full_name = f"Deleted user {actor_id.hex[:8]}"
            actor.phone = ""
            actor.telegram_username = None
            actor.contact_method = "none"
            actor.blocked_reason = None
            actor.status = "deleted"
            actor.deleted_at = utc_now()
            actor.anonymized_at = actor.deleted_at
            if actor_type == "performer":
                actor.about_text = None
                actor.is_accepting_orders = False
                actor.is_nearby_order_notifications_enabled = False
                actor.current_address_id = None
                actor.payment_recipient_id = None
            addresses = await uow.session.scalars(
                select(AddressModel).where(
                    (AddressModel.customer_id == actor_id)
                    if actor_type == "customer"
                    else (AddressModel.performer_id == actor_id)
                )
            )
            for address in addresses:
                address.address_text = ""
                address.fias_id = None
                address.latitude = None
                address.longitude = None
                address.entrance = None
                address.floor = None
                address.apartment = None
                address.comment = None
                address.deleted_at = utc_now()
                address.anonymized_at = address.deleted_at
            file_links = await uow.session.scalars(
                select(FileLinkModel).where(
                    FileLinkModel.entity_type == actor_type,
                    FileLinkModel.entity_id == actor_id,
                )
            )
            file_ids = [link.file_id for link in file_links]
            if file_ids:
                files = await uow.session.scalars(
                    select(FileModel).where(FileModel.id.in_(file_ids))
                )
                for file in files:
                    file.status = "deleted"
                    file.deleted_at = utc_now()
            record.status = "resolved"
            record.admin_comment = admin_comment
            record.resolved_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="anonymize_account",
                entity_type="account_deletion_request",
                entity_id=record_id,
                reason=admin_comment,
                audit_metadata={
                    "account_type": actor_type,
                    "account_id": str(actor_id),
                },
            )
            await uow.commit()
            return record

    @staticmethod
    def _support_model(record_kind: str) -> type[Any]:
        models = {
            "support": SupportRequestModel,
            "complaint": ComplaintModel,
            "dispute": DisputeModel,
            "deletion": AccountDeletionRequestModel,
        }
        try:
            return cast(type[Any], models[record_kind])
        except KeyError as exc:
            raise ValidationError("Invalid support record kind") from exc

    @staticmethod
    def _add_admin_panel_notification(
        *,
        session: Any,
        notification_type: str,
        entity_type: str,
        entity_id: UUID,
        deduplication_key: str,
    ) -> None:
        now = utc_now()
        session.add(
            NotificationModel(
                recipient_type="admin",
                admin_id=None,
                customer_id=None,
                performer_id=None,
                channel="admin_panel",
                type=notification_type,
                entity_type=entity_type,
                entity_id=entity_id,
                payload={"record_id": str(entity_id)},
                deduplication_key=deduplication_key,
                status="sent",
                attempts=0,
                scheduled_at=now,
                sent_at=now,
                delete_after=now + timedelta(days=30),
            ),
        )
