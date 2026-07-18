from backend.modules.admin.application import AdminDTO

from .schemas import AdminResponse


def admin_response(admin: AdminDTO) -> AdminResponse:
    return AdminResponse(
        id=str(admin.id),
        email=admin.email,
        full_name=admin.full_name,
        status=admin.status,
        last_login_at=admin.last_login_at.isoformat()
        if admin.last_login_at is not None
        else None,
    )
