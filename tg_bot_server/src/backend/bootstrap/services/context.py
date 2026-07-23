from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.bootstrap.settings import Settings
from backend.common.domain import ValidationError
from backend.common.infrastructure import S3ObjectStorage
from backend.common.infrastructure.database import SqlAlchemyUnitOfWork
from backend.modules.admin.infrastructure import RedisAdminSessionStore
from backend.modules.geo.infrastructure import DaDataGeocoder
from backend.modules.payments.infrastructure import (
    TBankPaymentGateway,
    TBankReceiptSettings,
)


@dataclass
class ServiceContext:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    storage: S3ObjectStorage
    geocoder: DaDataGeocoder
    _gateway: TBankPaymentGateway | None = None

    def uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def session_store(self) -> RedisAdminSessionStore:
        return RedisAdminSessionStore(
            redis=self.redis,
            ttl_seconds=self.settings.admin_session_ttl_seconds,
        )

    def payment_gateway(self) -> TBankPaymentGateway:
        if self._gateway is not None:
            return self._gateway
        if not self.settings.tbank_terminal_key or not self.settings.tbank_password:
            raise ValidationError("T-Bank payment credentials are not configured")
        if (
            self.settings.environment == "production"
            and self.settings.payment_receipt_defaults_allowed
        ):
            raise ValidationError(
                "Production payment receipt settings must be explicit"
            )
        self._gateway = TBankPaymentGateway(
            base_url=self.settings.tbank_base_url,
            terminal_key=self.settings.tbank_terminal_key,
            password=self.settings.tbank_password,
            notification_url=self.settings.tbank_notification_url or None,
            receipt=TBankReceiptSettings(
                taxation=self.settings.payment_receipt_taxation,
                tax=self.settings.payment_receipt_tax,
                payment_method=self.settings.payment_receipt_method,
                payment_object=self.settings.payment_receipt_object,
            ),
            timeout_seconds=self.settings.tbank_timeout_seconds,
        )
        return self._gateway


class Service:
    def __init__(self, context: ServiceContext) -> None:
        self.context = context

    def _uow(self) -> SqlAlchemyUnitOfWork:
        return self.context.uow()

    def _session_store(self) -> RedisAdminSessionStore:
        return self.context.session_store()

    def _geocoder(self) -> DaDataGeocoder:
        return self.context.geocoder

    def _storage(self) -> S3ObjectStorage:
        return self.context.storage

    def _payment_gateway(self) -> TBankPaymentGateway:
        return self.context.payment_gateway()
