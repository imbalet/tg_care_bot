from backend.modules.system_checks.application import SystemCheckRecordDTO

from .schemas import SystemCheckResponse


def system_check_response(record: SystemCheckRecordDTO) -> SystemCheckResponse:
    return SystemCheckResponse(
        id=str(record.id),
        name=record.name,
        created_at=record.created_at.isoformat(),
    )
