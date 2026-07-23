from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.bootstrap.resources import (
    create_database_engine,
    create_database_session_factory,
    create_geocoder,
    create_redis,
    create_storage,
)
from backend.bootstrap.services import (
    AdminServices,
    AvailabilityServices,
    CatalogServices,
    CustomerServices,
    GeoServices,
    OrderServices,
    PaymentServices,
    PerformerServices,
    ServiceContext,
    SupportServices,
    SystemCheckServices,
)
from backend.bootstrap.settings import Settings
from backend.common.infrastructure import S3ObjectStorage
from backend.modules.geo.infrastructure import DaDataGeocoder


@dataclass(frozen=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    storage: S3ObjectStorage
    geocoder: DaDataGeocoder
    context: ServiceContext = field(init=False)
    catalog: CatalogServices = field(init=False)
    geo: GeoServices = field(init=False)
    customers: CustomerServices = field(init=False)
    orders: OrderServices = field(init=False)
    payments: PaymentServices = field(init=False)
    availability: AvailabilityServices = field(init=False)
    performers: PerformerServices = field(init=False)
    support: SupportServices = field(init=False)
    admin: AdminServices = field(init=False)
    system_checks: SystemCheckServices = field(init=False)

    def __post_init__(self) -> None:
        context = ServiceContext(
            settings=self.settings,
            session_factory=self.session_factory,
            redis=self.redis,
            storage=self.storage,
            geocoder=self.geocoder,
        )
        payments = PaymentServices(context)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "catalog", CatalogServices(context))
        object.__setattr__(self, "geo", GeoServices(context))
        object.__setattr__(self, "customers", CustomerServices(context))
        object.__setattr__(self, "orders", OrderServices(context, payments))
        object.__setattr__(self, "payments", payments)
        object.__setattr__(self, "availability", AvailabilityServices(context))
        object.__setattr__(self, "performers", PerformerServices(context))
        object.__setattr__(self, "support", SupportServices(context))
        object.__setattr__(self, "admin", AdminServices(context))
        object.__setattr__(self, "system_checks", SystemCheckServices(context))

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def create_container(settings: Settings) -> Container:
    engine = create_database_engine(settings)
    session_factory = create_database_session_factory(engine)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        redis=create_redis(settings),
        storage=create_storage(settings),
        geocoder=create_geocoder(settings),
    )
