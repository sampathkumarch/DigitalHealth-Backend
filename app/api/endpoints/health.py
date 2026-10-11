from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_health_service, get_readiness_service
from app.schemas.health import HealthResponse
from app.services.health import HealthService
from app.services.readiness import ReadinessService

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


@router.get("/ready")
def ready(service: ReadinessService = Depends(get_readiness_service)) -> JSONResponse:
    report = service.check()
    body = {
        "status": report.status,
        "database": report.database,
        "redis": report.redis,
    }
    status_code = 200 if report.status == "ok" else 503
    return JSONResponse(status_code=status_code, content=body)
