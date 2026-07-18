import secrets
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Response
from sqlalchemy import select

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.application import utc_now
from backend.common.domain import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from backend.modules.admin.application import (
    GetCurrentAdminUseCase,
    LoginAdminCommand,
    LoginAdminUseCase,
    LogoutAdminUseCase,
)
from backend.modules.admin.infrastructure import (
    Argon2PasswordHasher,
    RedisAdminSessionStore,
    SqlAlchemyAdminAuditRepository,
    SqlAlchemyAdminRepository,
)
from backend.modules.catalog.infrastructure import BusinessSettingModel

from .mappers import admin_response
from .schemas import (
    AdminResponse,
    BusinessSettingResponse,
    LoginRequest,
    LoginResponse,
    UpdateBusinessSettingRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SESSION_COOKIE = "admin_session"
CSRF_HEADER = "X-CSRF-Token"


def _session_store(container: Container) -> RedisAdminSessionStore:
    return RedisAdminSessionStore(
        redis=container.redis,
        ttl_seconds=container.settings.admin_session_ttl_seconds,
    )


def _cookie_secure(container: Container) -> bool:
    return container.settings.environment == "production"


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    container: Annotated[Container, Depends(get_container)],
) -> LoginResponse:
    async with container.session_factory() as session:
        repository = SqlAlchemyAdminRepository(session)
        use_case = LoginAdminUseCase(
            repository=repository,
            password_hasher=Argon2PasswordHasher(),
            session_store=_session_store(container),
        )
        result = await use_case.execute(
            LoginAdminCommand(email=str(request.email), password=request.password),
        )
        await session.commit()
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=result.session_id,
        max_age=container.settings.admin_session_ttl_seconds,
        httponly=True,
        secure=_cookie_secure(container),
        samesite="lax",
        path="/admin",
    )
    return LoginResponse(
        admin=admin_response(result.admin),
        csrf_token=result.csrf_token,
    )


async def get_current_admin(
    container: Annotated[Container, Depends(get_container)],
    admin_session: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> tuple[AdminResponse, str, str]:
    if admin_session is None:
        raise AuthenticationError("Admin session is required")
    async with container.session_factory() as session:
        use_case = GetCurrentAdminUseCase(
            repository=SqlAlchemyAdminRepository(session),
            session_store=_session_store(container),
        )
        admin, csrf_token = await use_case.execute(admin_session)
    return (
        admin_response(admin),
        csrf_token,
        admin_session,
    )


async def require_admin_csrf(
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
    csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> tuple[AdminResponse, str, str]:
    expected = current[1]
    if csrf_token is None or not secrets.compare_digest(csrf_token, expected):
        raise AuthorizationError("CSRF token is invalid")
    return current


@router.get("/me")
async def me(
    current: Annotated[tuple[AdminResponse, str, str], Depends(get_current_admin)],
) -> AdminResponse:
    return current[0]


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> None:
    session_id = current[2]
    await LogoutAdminUseCase(_session_store(container)).execute(session_id)
    response.delete_cookie(ADMIN_SESSION_COOKIE, path="/admin")


@router.patch("/business-settings/{key}")
async def update_business_setting(
    key: str,
    request: UpdateBusinessSettingRequest,
    container: Annotated[Container, Depends(get_container)],
    current: Annotated[tuple[AdminResponse, str, str], Depends(require_admin_csrf)],
) -> BusinessSettingResponse:
    admin_id = UUID(current[0].id)
    async with container.session_factory() as session:
        result = await session.execute(
            select(BusinessSettingModel).where(BusinessSettingModel.key == key),
        )
        setting = result.scalar_one_or_none()
        if setting is None:
            raise NotFoundError("Business setting not found")
        value = _validated_setting_value(setting.value_type, request.value)
        old_value = setting.value
        setting.value = value
        setting.updated_by_admin_id = admin_id
        setting.updated_at = utc_now()
        await SqlAlchemyAdminAuditRepository(session).add(
            admin_id=admin_id,
            action="update_business_setting",
            entity_type="business_setting",
            entity_id=setting.id,
            audit_metadata={
                "key": key,
                "old_value": old_value,
                "new_value": value,
            },
        )
        response = BusinessSettingResponse(
            key=setting.key,
            value=setting.value,
            value_type=setting.value_type,
        )
        await session.commit()
    return response


def _validated_setting_value(value_type: str, value: object) -> object:
    if value is None:
        return None
    if value_type == "boolean":
        if not isinstance(value, bool):
            raise ValidationError("Business setting value must be boolean")
        return value
    if value_type in {"number", "integer", "decimal"}:
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            raise ValidationError("Business setting value must be numeric")
        try:
            Decimal(str(value))
        except InvalidOperation as exc:
            raise ValidationError("Business setting value must be numeric") from exc
        if value_type == "integer" and Decimal(str(value)) % 1:
            raise ValidationError("Business setting value must be integer")
        return value
    if value_type == "string":
        if not isinstance(value, str):
            raise ValidationError("Business setting value must be string")
        return value
    if value_type == "json":
        return value
    raise ValidationError("Business setting value type is invalid")
