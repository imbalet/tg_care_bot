import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Response
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.domain import AuthenticationError, AuthorizationError
from backend.modules.admin.application import (
    GetCurrentAdminUseCase,
    LoginAdminCommand,
    LoginAdminUseCase,
    LogoutAdminUseCase,
)
from backend.modules.admin.infrastructure import (
    Argon2PasswordHasher,
    RedisAdminSessionStore,
    SqlAlchemyAdminRepository,
)

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SESSION_COOKIE = "admin_session"
CSRF_HEADER = "X-CSRF-Token"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1)


class AdminResponse(BaseModel):
    id: str
    email: str
    full_name: str
    status: str
    last_login_at: str | None


class LoginResponse(BaseModel):
    admin: AdminResponse
    csrf_token: str


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
    admin = result.admin
    return LoginResponse(
        admin=AdminResponse(
            id=str(admin.id),
            email=admin.email,
            full_name=admin.full_name,
            status=admin.status,
            last_login_at=admin.last_login_at.isoformat()
            if admin.last_login_at is not None
            else None,
        ),
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
        AdminResponse(
            id=str(admin.id),
            email=admin.email,
            full_name=admin.full_name,
            status=admin.status,
            last_login_at=admin.last_login_at.isoformat()
            if admin.last_login_at is not None
            else None,
        ),
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


__all__ = [
    "ADMIN_SESSION_COOKIE",
    "CSRF_HEADER",
    "get_current_admin",
    "require_admin_csrf",
    "router",
]
