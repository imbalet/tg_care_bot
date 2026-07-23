from ._shared import (
    UUID,
    AccountDeletionRequestModel,
    Any,
    AuthorizationError,
    ComplaintModel,
    ConflictError,
    CustomerModel,
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


class SupportServices(Service):
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

    @staticmethod
    def _support_model(record_kind: str) -> type[Any]:
        models = {
            "support": SupportRequestModel,
            "complaint": ComplaintModel,
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
