from fastapi import APIRouter, Depends

from app.api.deps import get_health_service
from app.schemas.health import HealthResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    report = service.liveness()
    return HealthResponse(
        status=report.status,
        app=report.app_name,
        env=report.environment,
    )
